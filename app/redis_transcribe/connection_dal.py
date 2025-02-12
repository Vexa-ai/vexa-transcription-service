from datetime import datetime

from app.redis_transcribe import keys
from app.redis_transcribe.base import BaseDAL


class ConnectionDAL(BaseDAL):
    """Class for work with connection's data in Redis."""

    CONNECTION_KEY_NAME = keys.CONNECTION

    async def get_connection_data(self, connection_id: str) -> tuple:
        data = await self._redis_client.hgetall(f"{self.CONNECTION_KEY_NAME}:{connection_id}")
        start_timestamp = datetime.fromisoformat(data.get(keys.START_TIMESTAMP))
        end_timestamp = datetime.fromisoformat(data.get(keys.END_TIMESTAMP))
        return start_timestamp, end_timestamp

    async def set_start_timestamp(self, connection_id: str, start_timestamp: datetime) -> None:
        await self._redis_client.hset(
            f"{self.CONNECTION_KEY_NAME}:{connection_id}",
            keys.START_TIMESTAMP,
            start_timestamp.isoformat(),
        )

    async def set_end_timestamp(self, connection_id: str, start_timestamp: datetime) -> None:
        await self._redis_client.hset(
            f"{self.CONNECTION_KEY_NAME}:{connection_id}",
            keys.END_TIMESTAMP,
            start_timestamp.isoformat(),
        )

    def delete_connection_data(self, connection_id: str) -> None:
        self.delete_keys(f"{self.CONNECTION_KEY_NAME}:{connection_id}")
