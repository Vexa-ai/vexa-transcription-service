from app.redis_transcribe.connection import get_redis_client
from shared_lib.redis.dals.audio_chunk_dal import AudioChunkDAL

import logging
from datetime import datetime, timedelta, timezone
from typing import List
import os

from redis.asyncio.client import Redis

from app.services.audio.redis_models import Connection, Meeting, Transcriber
from app.settings import settings

from shared_lib.redis.models import AudioChunkModel, SpeakerDataModel

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        self.__running_tasks = set()
        self.__redis_client = None  # Will be initialized in setup

    async def setup(self):
        """Initialize Redis client if not already initialized."""
        if self.__redis_client is None:
            self.__redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        return self.__redis_client

    async def _get_new_connections(self):
        """Get new connections by scanning Redis for initialFeed_audio keys."""
        pattern = "initialFeed_audio:*"
        connections = []
        async for key in self.__redis_client.scan_iter(match=pattern):
            connection_id = key.split(':')[1]
            connections.append((connection_id, key))
        return connections

    async def process_connections(self):
        if not self.__redis_client:
            await self.setup()
        
        connections = await self._get_new_connections()
        for connection_id, key in connections:
            logger.info(f"Processing connection {connection_id}")
            await self._process_connection_task(connection_id)
            # Remove the key after processing
            await self.__redis_client.delete(key)

    async def _process_connection_task(
        self,
        connection_id,
        transcriber_step: int = None,
    ) -> None:
        # Use settings value if not provided
        if transcriber_step is None:
            transcriber_step = settings.transcriber_step_sec
        # Reuse the existing Redis client
        meeting_id, segment_start_user_timestamp, segment_end_user_timestamp, segment_start_server_timestamp, user_id = await self.writestream2file(connection_id)

        # If we didn't get valid data from writestream2file, skip processing
        if None in (meeting_id, segment_start_user_timestamp, segment_end_user_timestamp, segment_start_server_timestamp, user_id):
            logger.warning(f"Skipping processing for connection {connection_id} due to missing data")
            return

        current_time = datetime.now(timezone.utc) #TODO: consider using transcriber_last_updated_timestamp + step and rename to update_time

        connection = Connection(self.__redis_client, connection_id, user_id)
        await connection.update_timestamps(segment_start_user_timestamp, segment_end_user_timestamp)

        meeting = Meeting(self.__redis_client, meeting_id)

        await meeting.load_from_redis()
        await meeting.add_connection(connection.id)
        await meeting.set_start_timestamp(segment_start_user_timestamp)
        await meeting.set_start_server_timestamp(segment_start_server_timestamp)
        
        meeting.transcriber_last_updated_timestamp = (
            meeting.transcriber_last_updated_timestamp or segment_start_user_timestamp
        )

        time_since_last_update = (current_time - meeting.transcriber_last_updated_timestamp).seconds

        logger.info(f"Last transcriber update timestamp: {meeting.transcriber_last_updated_timestamp}")

        if time_since_last_update > transcriber_step:
            logger.info(f"Adding transcriber - time threshold exceeded ({time_since_last_update} > {transcriber_step} seconds)")
            transcriber = Transcriber(self.__redis_client)
            await transcriber.add_todo(meeting.meeting_id)
            await meeting.update_transcriber_timestamp(
                segment_start_user_timestamp, transcriber_last_updated_timestamp=current_time 
            )
        else:
            logger.info(f"Skipping transcriber addition - time threshold not met ({time_since_last_update} <= {transcriber_step} seconds)")

        await meeting.update_redis()

    async def writestream2file(self, connection_id):
        logger.info(f"Writing stream to file for connection {connection_id}")
        path = f"/data/audio/{connection_id}.webm"
        first_user_timestamp = None
        first_server_timestamp = None
        
        audio_chunk_dal = AudioChunkDAL(self.__redis_client)
        chunks = await audio_chunk_dal.pop_chunks(connection_id, limit=100)

        if not chunks:
            logger.info(f"No chunks found for connection {connection_id}")
            return None, None, None, None, None

        meeting_id = connection_id  # default if no meeting_id in data

        for chunk_data in chunks:
            try:
                chunk_obj = AudioChunkModel(**chunk_data)
            except ValueError as e:
                logger.error(f"Invalid chunk data for connection {connection_id}: {e}")
                continue

            raw_chunk = bytes.fromhex(chunk_obj.chunk)
            first_user_timestamp = (
                datetime.fromisoformat(chunk_obj.user_timestamp.rstrip("Z")).astimezone(timezone.utc)
                - timedelta(seconds=chunk_obj.audio_chunk_duration_sec)
                if not first_user_timestamp
                else first_user_timestamp
            )
            
            first_server_timestamp = (
                datetime.fromisoformat(chunk_obj.server_timestamp.rstrip("Z")).astimezone(timezone.utc)
                - timedelta(seconds=chunk_obj.audio_chunk_duration_sec)
                if not first_server_timestamp
                else first_server_timestamp
            )
            
            with open(path, "ab") as file:
                file.write(raw_chunk)

            last_user_timestamp = datetime.fromisoformat(chunk_obj.user_timestamp.rstrip("Z")).astimezone(timezone.utc)
            
            meeting_id = chunk_obj.meeting_id or connection_id
            user_id = str(chunk_obj.user_id)

        return meeting_id, first_user_timestamp, last_user_timestamp, first_server_timestamp, user_id