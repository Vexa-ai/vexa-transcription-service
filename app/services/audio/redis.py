import json
from dataclasses import dataclass
from typing import (
    Any,
    List,
    Literal,
    Optional,
    Union,
)

from redis.asyncio.client import Redis


@dataclass
class Data:
    key: str
    redis_client: Redis
    data: Union[List, dict] = None

    async def lpush(self):
        data = json.dumps(self.data)
        await self.redis_client.lpush(self.key, data)

    async def rpop(self):
        data = await self.redis_client.rpop(self.key)
        if data:
            self.data = json.loads(data)
        else:
            self.data = None
        return bool(data)

    async def delete(self):
        return bool(await self.redis_client.delete(self.key))

    # async def rpop_many(self, key: str, limit: int = 1, raise_exception: bool = False) -> Any:
    #     """Retrieves a specified number of audio chunks from this connection's queue in a FIFO manner using RPOP.

    #     Args:
    #         key: Key for getting data.
    #         limit: ToDo.
    #         raise_exception: ToDo.

    #     Returns:
    #         Data from redis converted to JSON.

    #     """
    #     # ToDo:
    #     #  if error put data in redis again
    #     #  if error_count > 5 put data in difference
    #     chunks = []

    #     # Continuously remove items from the right end of the list (end of the list)
    #     for _ in range(limit):
    #         chunk = await self.__redis_client.rpop(key)
    #         if chunk:
    #             chunks.append(json.loads(chunk))
    #         else:
    #             break  # Exit if the list becomes empty before reaching num_items

    #     if chunks:
    #         return chunks

    #     if raise_exception:
    #         raise DataNotFoundError(f"Data for '{key}' not found")


class Transcript(Data):
    def __init__(self, meeting_id: str, redis_client: Redis, data: List = None):
        super().__init__(key=f"Transcript:{meeting_id}", redis_client=redis_client, data=data)


class Diarisation(Data):
    def __init__(self, meeting_id: str, redis_client: Redis, data: List = None):
        super().__init__(key=f"Diarisation:{meeting_id}", redis_client=redis_client, data=data)


class Connection:
    def __init__(self, redis_client: Redis, connection_id, user_id=None):
        self.redis = redis_client
        self.id = connection_id
        self.type_ = f"connection:{connection_id}"
        self.path = f"/audio/{connection_id}.webm"
        self.start_timestamp = None
        self.end_timestamp = None
        self.user_id = user_id

    def update_redis(self):
        if self.start_timestamp is not None:
            self.redis.hset(self.type_, "start_timestamp", self.start_timestamp)
        if self.user_id is not None:
            self.redis.hset(self.type_, "user_id", self.user_id)

    def load_from_redis(self):
        data = self.redis.hgetall(self.type_)
        self.start_timestamp = data.get("start_timestamp")
        self.user_id = data.get("user_id")

    def delete_connection_data(self):
        self.redis.delete(self.type_)

    def update_timestamps(self, segment_start_timestamp, end_timestamp):
        self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if not self.start_timestamp else self.start_timestamp
        self.end_timestamp = end_timestamp
        self.update_redis()


class Meeting:
    def __init__(self, redis_client: Redis, meeting_id: str):
        self.redis = redis_client
        self.meeting_id = meeting_id
        self.metadata_type_ = f"meeting:{meeting_id}:metadata"
        self.connections_type_ = f"meeting:{meeting_id}:connections"
        self.start_timestamp: Optional[Any] = None
        self.diarize_seek_timestamp: Optional[Any] = None
        self.transcribe_seek_timestamp: Optional[Any] = None
        self.last_updated_timestamp: Optional[Any] = None

        self.timestamps = [
            "start_timestamp",
            "diarize_seek_timestamp",
            "transcribe_seek_timestamp",
            "last_updated_timestamp",
        ]

    async def _update_field(self, field_name: str, value: Optional[Any]):
        # update redis only if not none
        if value is not None:
            await self.redis.hset(self.metadata_type_, field_name, value)

    async def _load_field(self, data: dict, field_name: str, default_value: Optional[Any] = None):
        # replace from redis only if none
        value = data.get(field_name)
        setattr(self, field_name, value if value is not None else default_value)

    async def update_redis(self):
        for t in self.timestamps:
            await self._update_field(t, getattr(self, t))

    async def load_from_redis(self):
        data = await self.redis.hgetall(self.metadata_type_)
        for t in self.timestamps:
            await self._load_field(data, t, self.start_timestamp)

    def add_connection(self, connection_id):
        self.redis.sadd(self.connections_type_, connection_id)

    def get_connections(self):
        return self.redis.smembers(self.connections_type_)

    def pop_connection(self):
        return self.redis.spop(self.connections_type_)

    def update_timestamps(self, segment_start_timestamp, last_updated_timestamp):
        self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if self.start_timestamp is None else self.start_timestamp
        self.last_updated_timestamp = last_updated_timestamp
        self.update_redis()


class ProcessorManager:
    def __init__(self, redis_client: Redis, processor_type: Literal["Diarize", "Transcribe"]):
        self.redis = redis_client
        self.processor_type = processor_type
        self.todo_type_ = f"{processor_type.lower()}:todo"
        self.in_progress_type_ = f"{processor_type.lower()}:in_progress"

    async def add_todo(self, task_id: str):
        await self.redis.sadd(self.todo_type_, task_id)

    async def pop_inprogress(self) -> Union[str, None]:
        task_id = await self.redis.spop(self.todo_type_)
        if task_id:
            await self.redis.sadd(self.in_progress_type_, task_id)
        return task_id

    async def remove_from_in_progress(self, task_id: str):
        await self.redis.srem(self.in_progress_type_, task_id)


class Diarizer(ProcessorManager):
    def __init__(self, redis_client: Redis):
        super().__init__(redis_client, "Diarize")


class Transcriber(ProcessorManager):
    def __init__(self, redis_client: Redis):
        super().__init__(redis_client, "Transcribe")
