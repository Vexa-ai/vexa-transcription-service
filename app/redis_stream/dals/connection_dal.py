"""Module for work with Redis by connection key."""
import logging
from typing import List

from app.redis_stream.dals.base import BaseDAL
from app.redis_stream.keys import CONNECTION_TIMESTAMP, NEW_CONNECTIONS_INFO

logger = logging.getLogger(__name__)


class ConnectionDAL(BaseDAL):
    """Class for basic work with Redis by connection key."""



    async def get_connection_timestamps(self, limit: int = 100) -> dict:
        # Ensure decoding if needed
        raw_data = await self.rpop_many_by_pattern(name=f"{CONNECTION_TIMESTAMP}:", limit=limit)
        return {key.split(":")[-1]: value for key, value in raw_data.items()}  # Ensure decoding if needed


    async def add_connection_timestamp(self, connection_id: str, timestamp: str) -> None:
        await self._redis_client.lpush(f"{CONNECTION_TIMESTAMP}:{connection_id}", timestamp)
