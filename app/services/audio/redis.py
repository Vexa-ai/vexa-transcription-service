import json
from dataclasses import dataclass
from typing import List, Literal, Union

from redis.asyncio.client import Redis

from typing import Optional, Any


class Connection:
    def __init__(self, redis_client: Redis, connection_id, user_id=None):
        self.redis = redis_client
        self.id = connection_id
        self.key = f"connection:{connection_id}"
        self.path = f"/audio/{connection_id}.webm"
        self.start_timestamp = None
        self.end_timestamp = None
        self.user_id = user_id


    def update_redis(self):
        if self.start_timestamp is not None:
            self.redis.hset(self.key, "start_timestamp", self.start_timestamp)
        if self.user_id is not None:
            self.redis.hset(self.key, "user_id", self.user_id)


    def load_from_redis(self):
        data = self.redis.hgetall(self.key)
        self.start_timestamp = data.get("start_timestamp")
        self.user_id = data.get("user_id")

    
    def delete_connection_data(self):
        self.redis.delete(self.key)
        
    def update_timestamps(self, segment_start_timestamp,end_timestamp):
        self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if not self.start_timestamp  else self.start_timestamp
        self.end_timestamp = end_timestamp
        self.update_redis()


class Meeting:
    def __init__(self, redis_client: Redis, meeting_id: str):
        self.redis = redis_client
        self.meeting_id = meeting_id
        self.metadata_key = f"meeting:{meeting_id}:metadata"
        self.connections_key = f"meeting:{meeting_id}:connections"
        self.start_timestamp: Optional[Any] = None
        self.diarize_seek_timestamp: Optional[Any] = None
        self.transcribe_seek_timestamp: Optional[Any] = None
        self.last_updated_timestamp: Optional[Any] = None


    async def _update_field(self, field_name: str, value: Optional[Any]):
        if value is not None:
            await self.redis.hset(self.metadata_key, field_name, value)

    async def _load_field(self, data: dict, field_name: str, default_value: Optional[Any] = None):
        value = data.get(field_name.encode())
        setattr(self, field_name, value if value is not None else default_value)

    async def update_redis(self):
        await self._update_field("start_timestamp", self.start_timestamp)
        await self._update_field("diarize_seek_timestamp", self.diarize_seek_timestamp)
        await self._update_field("transcribe_seek_timestamp", self.transcribe_seek_timestamp)
        await self._update_field("last_updated_timestamp", self.last_updated_timestamp)

    async def load_from_redis(self):
        data = await self.redis.hgetall(self.metadata_key)
        await self._load_field(data, "start_timestamp")
        await self._load_field(data, "diarize_seek_timestamp", self.start_timestamp)
        await self._load_field(data, "transcribe_seek_timestamp", self.start_timestamp)
        await self._load_field(data, "last_updated_timestamp", self.start_timestamp)


    def add_connection(self, connection_id):
        self.redis.sadd(self.connections_key, connection_id)

    def get_connections(self):
        return self.redis.smembers(self.connections_key)

    def pop_connection(self):
        return self.redis.spop(self.connections_key)
    
    
    def update_timestamps(self, segment_start_timestamp, last_updated_timestamp):
        self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if self.start_timestamp is None else self.start_timestamp
        self.last_updated_timestamp = last_updated_timestamp
        self.update_redis()
        
        
class ProcessorManager:
    def __init__(self, redis_client: Redis, processor_type: Literal["Diarize", "Transcribe"]):
        self.redis = redis_client
        self.processor_type = processor_type
        self.todo_key = f"{processor_type.lower()}:todo"
        self.in_progress_key = f"{processor_type.lower()}:in_progress"

    async def add_todo(self, task_id: str):
        await self.redis.sadd(self.todo_key, task_id)

    async def pop_inprogress(self) -> Union[str, None]:
        task_id = await self.redis.spop(self.todo_key)
        if task_id:
            await self.redis.sadd(self.in_progress_key, task_id)
        return task_id

    async def remove_from_in_progress(self, task_id: str):
        await self.redis.srem(self.in_progress_key, task_id)
        
        
        
class Diarizer(ProcessorManager):
    def __init__(self, redis_client: Redis):
        super().__init__(redis_client, "Diarize")


class Transcriber(ProcessorManager):
    def __init__(self, redis_client: Redis):
        super().__init__(redis_client, "Transcribe")
