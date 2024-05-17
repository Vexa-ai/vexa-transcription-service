import asyncio
import json
import logging
import uuid
import datetime

from app.database_redis.connection import get_redis_client
from app.services.apis.streamqueue_service.client import StreamQueueServiceAPI
from app.services.audio.audio import AudioSlicer
from app.services.audio.redis import Connection, Meeting, Diarizer, Transcriber
from app.settings import settings


logger = logging.getLogger(__name__)



class Processor:
    def __init__(self):
        self.__running_tasks = set()
        self.__stream_queue_service_api = StreamQueueServiceAPI()

    async def process_connections(self):
        
        
        connections = await self.__stream_queue_service_api.get_connections()
        connection_ids = [c[0] for c in connections]

        for connection_id in connection_ids:
            await self._process_connection_task(self,connection_id)


    async def _process_connection_task(self, connection_id, diarizer_step=60, transcriber_step=5, max_length=240):
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        

        meeting_id, segment_start_timestamp, segment_end_timestamp, user_id = await self.__writestream2file(connection_id) 
        ≠
        connection = Connection(redis_client,connection_id, user_id)
        connection.update_timestamps(segment_start_timestamp,segment_end_timestamp)
        
        meeting = Meeting(redis_client, meeting_id)
        meeting.load_from_redis()
   
        meeting.add_connection(connection.id)
        
        
        if datetime.utcnow() - max(meeting.last_updated_timestamp, meeting.diarize_seek_timestamp) > diarizer_step:
            diarizer = Diarizer(redis_client)
            diarizer.add_todo(meeting.id)
            
            
        if datetime.utcnow() - max(meeting.last_updated_timestamp, meeting.transcribe_seek_timestamp) > transcriber_step:
            transcriber = Transcriber(redis_client)
            transcriber.add_todo(meeting.id)
            
        
        
        meeting.update_timestamps(segment_start_timestamp,datetime.utcnow())
        
        
    

    async def __writestream2file(self, connection_id):
        path = f"/audio/{connection_id}.webm"
        first_timestamp = None
        items = await self.__stream_queue_service_api.fetch_chunks(connection_id, num_chunks=100)

        if items:
            for item in items["chunks"]:
                chunk = bytes.fromhex(item["chunk"])
                first_timestamp = item["timestamp"] if not first_timestamp else first_timestamp

                # Open the file in append mode
                with open(path, "ab") as file:
                    # Write data to the file
                    file.write(chunk)

                last_timestamp = item["timestamp"]
                meeting_id = item["meeting_id"]
                client_id = item["client_id"] #thi

            return meeting_id, first_timestamp, last_timestamp, client_id
