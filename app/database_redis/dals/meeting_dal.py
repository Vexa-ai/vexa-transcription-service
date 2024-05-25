from app.database_redis import keys
from app.database_redis.dals.base import BaseDAL


class MeetingDAL(BaseDAL):
    """Class for work with meeting's data in Redis."""

    MEETING_KEY_NAME = keys.MEETING
    TIMESTAMPS_KEYS = [
        keys.START_TIMESTAMP,
        keys.DIARIZE_SEEK_TIMESTAMP,
        keys.TRANSCRIBE_SEEK_TIMESTAMP,
        keys.TRANSCRIBER_LAST_UPDATED_TIMESTAMP,
        keys.DIARIZER_LAST_UPDATED_TIMESTAMP,
    ]

    async def get_meeting_timestamps(self, meeting_id: str):
        data = await self._redis_client.hgetall(f"{self.MEETING_KEY_NAME}:{meeting_id}:metadata")
        return [data.get(timestamp_key) for timestamp_key in self.TIMESTAMPS_KEYS]

    async def set_start_timestamp(self, meeting_id: str):
        data = await self._redis_client.hgetall(f"{self.MEETING_KEY_NAME}:{meeting_id}:metadata")
        return [data.get(timestamp_key) for timestamp_key in self.TIMESTAMPS_KEYS]

    async def set_diarize_seek_timestamp(self, meeting_id: str):
        data = await self._redis_client.hgetall(f"{self.MEETING_KEY_NAME}:{meeting_id}:metadata")
        return [data.get(timestamp_key) for timestamp_key in self.TIMESTAMPS_KEYS]

    async def set_transcribe_seek_timestamp(self, meeting_id: str):
        data = await self._redis_client.hgetall(f"{self.MEETING_KEY_NAME}:{meeting_id}:metadata")
        return [data.get(timestamp_key) for timestamp_key in self.TIMESTAMPS_KEYS]

    async def set_transcriber_last_updated_timestamp(self, meeting_id: str):
        data = await self._redis_client.hgetall(f"{self.MEETING_KEY_NAME}:{meeting_id}:metadata")
        return [data.get(timestamp_key) for timestamp_key in self.TIMESTAMPS_KEYS]

    async def set_diarizer_last_updated_timestamp(self, meeting_id: str):
        data = await self._redis_client.hgetall(f"{self.MEETING_KEY_NAME}:{meeting_id}:metadata")
        return [data.get(timestamp_key) for timestamp_key in self.TIMESTAMPS_KEYS]
