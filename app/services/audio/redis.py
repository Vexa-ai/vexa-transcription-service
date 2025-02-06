import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional, Union

from dateutil import parser
from dateutil.tz import UTC
from redis.asyncio.client import Redis

from app.clients.database_redis.keys import SEGMENTS_DIARIZE, SEGMENTS_TRANSCRIBE

logger = logging.getLogger(__name__)


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
        return data

    async def delete(self):
        return bool(await self.redis_client.delete(self.key))


class Transcript(Data):
    def __init__(self, meeting_id: str, redis_client: Redis, data: List = None):
        super().__init__(key=f"{SEGMENTS_TRANSCRIBE}:{meeting_id}", redis_client=redis_client, data=data)


class Connection:
    def __init__(self, redis_client: Redis, connection_id, user_id=None):
        self.redis = redis_client
        self.id = connection_id
        self.user_id = user_id
        self.type_ = f"connection:{connection_id}"
        self.path = f"/audio/{connection_id}.webm"

        self.start_timestamp = None
        self.end_timestamp = None

    async def update_redis(self):
        if self.start_timestamp is not None:
            await self.redis.hset(self.type_, "start_timestamp", self.start_timestamp.isoformat())
        if self.end_timestamp is not None:
            await self.redis.hset(self.type_, "end_timestamp", self.end_timestamp.isoformat())
        if self.user_id is not None:
            await self.redis.hset(self.type_, "user_id", self.user_id)

    async def load_from_redis(self):
        data = await self.redis.hgetall(self.type_)
        if data:
            self.start_timestamp = parser.parse(data.get("start_timestamp")).astimezone(UTC)
            self.end_timestamp = parser.parse(data.get("end_timestamp")).astimezone(UTC)
            self.user_id = data.get("user_id")

    async def delete_connection_data(self):
        await self.redis.delete(self.type_)

    async def update_timestamps(self, segment_start_timestamp, end_timestamp):
        await self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if not self.start_timestamp else self.start_timestamp
        self.end_timestamp = end_timestamp
        await self.update_redis()


class Meeting:
    def __init__(self, redis_client: Redis, meeting_id: str):
        self.redis = redis_client
        self.meeting_id = meeting_id
        self.metadata_type_ = f"meeting:{meeting_id}:metadata"
        self.connections_type_ = f"meeting:{meeting_id}:connections"

        self.start_timestamp: Optional[datetime] = None
        self.diarizer_seek_timestamp: Optional[datetime] = None
        self.transcriber_seek_timestamp: Optional[datetime] = None
        self.transcriber_last_updated_timestamp: Optional[datetime] = None
        self.diarizer_last_updated_timestamp: Optional[datetime] = None
        self.timestamps = [
            "start_timestamp",
            "diarizer_seek_timestamp",
            "transcriber_seek_timestamp",
            "transcriber_last_updated_timestamp",
            "diarizer_last_updated_timestamp",
        ]

    async def _update_field(self, field_name: str, value: Optional[datetime]):
        # update redis only if not none
        if value is not None:
            await self.redis.hset(self.metadata_type_, field_name, value.isoformat())

    async def _load_field(self, data: dict, field_name: str, default_value: Optional[datetime] = None):
        value = data.get(field_name)
        set_value = default_value
        if value is not None:
            set_value = parser.parse(value).astimezone(UTC)
        setattr(self, field_name, set_value)

    async def update_redis(self):
        for t in self.timestamps:
            await self._update_field(t, getattr(self, t))

    async def load_from_redis(self):
        data = await self.redis.hgetall(self.metadata_type_)
        for t in self.timestamps:
            await self._load_field(data, t, self.start_timestamp)

    async def add_connection(self, connection_id):
        await self.redis.sadd(self.connections_type_, connection_id)

    async def delete_connection(self, connection_id):
        await self.redis.srem(self.connections_type_, connection_id)

    async def get_connections(self):
        connection_ids = await self.redis.smembers(self.connections_type_)
        connections = [Connection(self.redis, id) for id in connection_ids]
        [await c.load_from_redis() for c in connections]
        return connections

    def pop_connection(self):
        return self.redis.spop(self.connections_type_)

    async def set_start_timestamp(self, segment_start_timestamp):
        await self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if self.start_timestamp is None else self.start_timestamp

        await self.update_redis()

    async def update_diarizer_timestamp(self, segment_start_timestamp, diarizer_last_updated_timestamp):
        await self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if self.start_timestamp is None else self.start_timestamp
        self.diarizer_last_updated_timestamp = (
            diarizer_last_updated_timestamp if diarizer_last_updated_timestamp else None
        )
        await self.update_redis()

    async def update_transcriber_timestamp(self, segment_start_timestamp, transcriber_last_updated_timestamp):
        await self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if self.start_timestamp is None else self.start_timestamp
        self.transcriber_last_updated_timestamp = (
            transcriber_last_updated_timestamp if transcriber_last_updated_timestamp else None
        )
        await self.update_redis()

    async def delete_meeting_data(self):
        await self.redis.delete(self.metadata_type_)
        await self.redis.delete(self.connections_type_)


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

    async def remove(self, task_id: str):
        await self.redis.srem(self.in_progress_type_, task_id)


class Transcriber(ProcessorManager):
    def __init__(self, redis_client: Redis):
        super().__init__(redis_client, "Transcribe")


# funcs to determing connection that best overlap the target period
def get_timestamps_overlap(start1, end1, start2, end2):
    latest_start = max(start1, start2)
    earliest_end = min(end1, end2)
    delta = (earliest_end - latest_start).total_seconds()
    return max(0, delta)


# def best_covering_connection(target_start, target_end, connections):
#     #TODO: change if to choose between connections that are 1 minimimize gap between target start and connection start 2 maximum overlap
#     best_connection = None
#     max_overlap = 0

#     for connection in connections:
#         overlap = get_timestamps_overlap(target_start, target_end, connection.start_timestamp, connection.end_timestamp)
#         if overlap > max_overlap:
#             max_overlap = overlap
#             best_connection = connection

#     return best_connection


def best_covering_connection(target_start, target_end, connections):
    best_connection = None
    # max_overlap = 0
    min_start_diff = float("inf")
    overlapped_connections = []

    # Find all connections that overlap with the target interval
    for connection in connections:
        overlap = get_timestamps_overlap(target_start, target_end, connection.start_timestamp, connection.end_timestamp)
        if overlap > 0:
            overlapped_connections.append(connection)

    # If there are no overlapping connections, return None
    if not overlapped_connections:
        return None

    # Among the overlapping connections, find the one closest to the target start time
    for connection in overlapped_connections:
        start_diff = abs((target_start - connection.start_timestamp).total_seconds())
        if start_diff < min_start_diff:
            min_start_diff = start_diff
            best_connection = connection

    return best_connection


def connection_with_minimal_start_greater_than_target(target_start, connections):
    best_connection = None
    min_start_timestamp = None

    for connection in connections:
        if connection.start_timestamp > target_start:
            if min_start_timestamp is None or connection.start_timestamp < min_start_timestamp:
                min_start_timestamp = connection.start_timestamp
                best_connection = connection

    return best_connection
