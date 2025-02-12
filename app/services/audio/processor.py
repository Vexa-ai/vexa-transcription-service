from app.redis_transcribe.connection import get_redis_client
from app.redis_stream.dals.connection_dal import ConnectionDAL
from app.redis_stream.dals.audio_chunk_dal import AudioChunkDAL

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from redis.asyncio.client import Redis

from app.services.audio.redis_models import Connection, Meeting, Transcriber
from app.settings import settings

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        self.__running_tasks = set()

    async def process_connections(self):
        logger.info("Process connections...")
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        connection_dal = ConnectionDAL(redis_client)
        connections = await connection_dal.get_new_connections()

        for connection in connections:
            logger.info(f"Processing connection {connection['connection_id']}")
            await self._process_connection_task(connection['connection_id'])

    async def _process_connection_task(
        self,
        connection_id,
        transcriber_step: int = 10,
    ) -> None:
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        meeting_id, segment_start_timestamp, segment_end_timestamp, user_id = await self.writestream2file(connection_id)

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
        path = f"/audio/{connection_id}.webm"
        first_timestamp = None
        
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        audio_chunk_dal = AudioChunkDAL(redis_client)
        chunks = await audio_chunk_dal.pop_chunks(connection_id, limit=100)

        if chunks:
            meeting_id = connection_id  # default if no meeting_id in data

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
