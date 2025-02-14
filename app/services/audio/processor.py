from app.redis_transcribe.connection import get_redis_client
from app.redis_stream.dals.audio_chunk_dal import AudioChunkDAL

import logging
from datetime import datetime, timedelta, timezone
from typing import List
import os

from redis.asyncio.client import Redis

from app.services.audio.redis_models import Connection, Meeting, Transcriber
from app.settings import settings

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        self.__running_tasks = set()

    async def _get_new_connections(self, redis_client: Redis):
        """Get new connections by scanning Redis for initialFeed_audio keys."""
        pattern = "initialFeed_audio:*"
        connections = []
        async for key in redis_client.scan_iter(match=pattern):
            connection_id = key.split(':')[1]
            connections.append((connection_id, key))
        return connections

    async def process_connections(self):
        logger.info("Process connections...")
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        
        connections = await self._get_new_connections(redis_client)
        for connection_id, key in connections:
            logger.info(f"Processing connection {connection_id}")
            await self._process_connection_task(connection_id)
            # Remove the key after processing
            await redis_client.delete(key)

    async def _process_connection_task(
        self,
        connection_id,
        transcriber_step: int = 10,
    ) -> None:
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        meeting_id, segment_start_timestamp, segment_end_timestamp, user_id = await self.writestream2file(connection_id)

        # If we didn't get valid data from writestream2file, skip processing
        if None in (meeting_id, segment_start_timestamp, segment_end_timestamp, user_id):
            logger.warning(f"Skipping processing for connection {connection_id} due to missing data")
            return

        current_time = datetime.now(timezone.utc)

        connection = Connection(redis_client, connection_id, user_id)
        await connection.update_timestamps(segment_start_timestamp, segment_end_timestamp)

        meeting = Meeting(redis_client, meeting_id)

        await meeting.load_from_redis()
        await meeting.add_connection(connection.id)
        await meeting.set_start_timestamp(segment_start_timestamp)

        meeting.transcriber_last_updated_timestamp = (
            meeting.transcriber_last_updated_timestamp or segment_start_timestamp
        )


        if (current_time - meeting.transcriber_last_updated_timestamp).seconds > transcriber_step:
            logger.info("transcriber added")
            transcriber = Transcriber(redis_client)
            await transcriber.add_todo(meeting.meeting_id)
            await meeting.update_transcriber_timestamp(
                segment_start_timestamp, transcriber_last_updated_timestamp=current_time
            )

        await meeting.update_redis()

    async def writestream2file(self, connection_id):
        logger.info(f"Writing stream to file for connection {connection_id}")
        path = f"/data/audio/{connection_id}.webm"
        first_timestamp = None
        
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        audio_chunk_dal = AudioChunkDAL(redis_client)
        chunks = await audio_chunk_dal.pop_chunks(connection_id, limit=100)

        if chunks:
            meeting_id = connection_id  # default if no meeting_id in data
            
            # Check if file exists - if not, ensure first chunk has index 0
            if not os.path.exists(path):
                first_chunk = chunks[0]
                logger.info(f"First chunk data for new file {connection_id}: {first_chunk}")
                if 'audio_chunk_number' not in first_chunk:
                    logger.warning(f"audio_chunk_number field missing in first chunk for connection {connection_id}")
                    return None, None, None, None
                if first_chunk['audio_chunk_number'] != 0:
                    logger.warning(f"First chunk index is {first_chunk['audio_chunk_number']} instead of 0 for connection {connection_id}")
                    return None, None, None, None

            for chunk_data in chunks:
                chunk = bytes.fromhex(chunk_data['chunk'])
                first_timestamp: datetime = (
                    datetime.fromisoformat(chunk_data['timestamp'].rstrip("Z")).astimezone(timezone.utc)
                    - timedelta(seconds=chunk_data['audio_chunk_duration_sec'])
                    if not first_timestamp
                    else first_timestamp
                )

                # Open the file in append mode
                with open(path, "ab") as file:
                    file.write(chunk)

                last_timestamp = datetime.fromisoformat(chunk_data['timestamp'].rstrip("Z")).astimezone(timezone.utc)
                meeting_id = chunk_data['meeting_id']
                user_id = chunk_data['user_id']

            return meeting_id, first_timestamp, last_timestamp, user_id

    @staticmethod
    async def __save_timestamps(
        redis_client: Redis,
        connection_id: str,
        segment_start_timestamp: datetime,
        segment_end_timestamp: datetime,
    ):
        connection = ConnectionDAL(redis_client)
        start_timestamp, end_timestamp = await connection.get_connection_data(connection_id)
        if start_timestamp is None:
            await connection.set_start_timestamp(connection_id, segment_start_timestamp)

        if end_timestamp is None:
            await connection.set_end_timestamp(connection_id, segment_end_timestamp)
