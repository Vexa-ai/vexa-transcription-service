import logging
from datetime import datetime, timezone
from typing import List

from redis.asyncio import Redis

from app.database_redis.connection import get_redis_client
from app.database_redis.dals.connection_dal import ConnectionDAL
from app.services.apis.streamqueue_service.client import StreamQueueServiceAPI
from app.services.apis.streamqueue_service.schemas import AudioChunkInfo
from app.services.audio.redis import Connection, Diarizer, Meeting, Transcriber
from app.settings import settings

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        self.__running_tasks = set()
        self.stream_queue_service_api = StreamQueueServiceAPI()

    async def process_connections(self):
        logger.info("Process connections...")
        connections = await self.stream_queue_service_api.get_connections()
        connection_ids = [c.connection_id for c in connections]

        for connection_id in connection_ids:
            await self._process_connection_task(connection_id)

    async def _process_connection_task(self, connection_id, diarizer_step=10, transcriber_step=5):
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        meeting_id, segment_start_timestamp, segment_end_timestamp, user_id = await self.writestream2file(connection_id)

        current_time = datetime.now(timezone.utc)

        connection = Connection(redis_client, connection_id, user_id)
        await connection.update_timestamps(segment_start_timestamp, segment_end_timestamp)

        meeting = Meeting(redis_client, meeting_id)

        await meeting.load_from_redis()
        await meeting.add_connection(connection.id)
        await meeting.set_start_timestamp(segment_start_timestamp)

        meeting.diarizer_last_updated_timestamp = meeting.diarizer_last_updated_timestamp or segment_start_timestamp
        meeting.transcriber_last_updated_timestamp = (
            meeting.transcriber_last_updated_timestamp or segment_start_timestamp
        )

        if (current_time - meeting.diarizer_last_updated_timestamp).seconds > diarizer_step:
            print("diarizer added")
            diarizer = Diarizer(redis_client)
            await diarizer.add_todo(meeting.meeting_id)
            await meeting.update_diarizer_timestamp(
                segment_start_timestamp, diarizer_last_updated_timestamp=current_time
            )

        if (current_time - meeting.transcriber_last_updated_timestamp).seconds > transcriber_step:
            print("transcriber added")
            transcriber = Transcriber(redis_client)
            await transcriber.add_todo(meeting.meeting_id)
            await meeting.update_transcriber_timestamp(
                segment_start_timestamp, transcriber_last_updated_timestamp=current_time
            )

        await meeting.update_redis()

    async def writestream2file(self, connection_id):
        path = f"/audio/{connection_id}.webm"
        first_timestamp = None
        items: List[AudioChunkInfo] = await self.stream_queue_service_api.fetch_chunks(connection_id, limit=100)

        if items:
            # if there is no meeting_id in META-data
            meeting_id = connection_id

            for item in items:
                chunk = bytes.fromhex(item.chunk)
                first_timestamp = (
                    datetime.fromisoformat(item.timestamp.rstrip("Z")).astimezone(timezone.utc)
                    if not first_timestamp
                    else first_timestamp
                )

                # Open the file in append mode
                with open(path, "ab") as file:
                    # Write data to the file
                    file.write(chunk)

                last_timestamp = datetime.fromisoformat(item.timestamp.rstrip("Z")).astimezone(timezone.utc)
                meeting_id = item.meeting_id
                user_id = item.user_id

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
