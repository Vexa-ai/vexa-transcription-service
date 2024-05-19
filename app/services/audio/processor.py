import logging
from datetime import datetime, timezone

from app.database_redis.connection import get_redis_client
from app.services.apis.streamqueue_service.client import StreamQueueServiceAPI
from app.services.audio.redis import Connection, Diarizer, Meeting, Transcriber
from app.settings import settings

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        self.__running_tasks = set()
        self.__stream_queue_service_api = StreamQueueServiceAPI()

    async def process_connections(self):
        logger.info("Process connections...")
        connections = await self.__stream_queue_service_api.get_connections()
        connection_ids = [c[0] for c in connections]

        for connection_id in connection_ids:
            await self._process_connection_task(connection_id)

    async def _process_connection_task(self, connection_id, diarizer_step=60, transcriber_step=5):
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)

        meeting_id, segment_start_timestamp, segment_end_timestamp, user_id = await self.__writestream2file(
            connection_id
        )
        current_time = datetime.now(timezone.utc)

        connection = Connection(redis_client, connection_id, user_id)
        await connection.update_timestamps(segment_start_timestamp, segment_end_timestamp)

        meeting = Meeting(redis_client, meeting_id)
        await meeting.load_from_redis()
        await meeting.add_connection(connection.id)

        if (current_time - meeting.diarizer_last_updated_timestamp).seconds > diarizer_step:
            diarizer = Diarizer(redis_client)
            await diarizer.add_todo(meeting.meeting_id)
            meeting.update_diarizer_timestamp(segment_start_timestamp, diarizer_last_updated_timestamp=current_time)

        if (current_time - meeting.transcriber_last_updated_timestamp).seconds > transcriber_step:
            transcriber = Transcriber(redis_client)
            await transcriber.add_todo(meeting.meeting_id)
            meeting.update_transcriber_timestamp(segment_start_timestamp, transcriber_last_updated_timestamp=current_time)

    async def __writestream2file(self, connection_id):
        path = f"/audio/{connection_id}.webm"
        first_timestamp = None
        items = await self.__stream_queue_service_api.fetch_chunks(connection_id, num_chunks=100)

        if items:
            # if there is no meeting_id in META-data
            meeting_id = connection_id

            for item in items["chunks"]:
                chunk = bytes.fromhex(item["chunk"])
                first_timestamp = item["timestamp"] if not first_timestamp else first_timestamp

                # Open the file in append mode
                with open(path, "ab") as file:
                    # Write data to the file
                    file.write(chunk)

                last_timestamp = item["timestamp"]
                meeting_id = item["meeting_id"]
                user_id = item["user_id"]

            return meeting_id, first_timestamp, last_timestamp, user_id
