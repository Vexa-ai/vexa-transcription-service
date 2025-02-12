"""Module for work with Redis by connection key."""
import logging
from typing import List

from app.redis_stream.dals.base import BaseDAL
from app.redis_stream.keys import CONNECTION_TIMESTAMP, NEW_CONNECTIONS_INFO

logger = logging.getLogger(__name__)


class ConnectionDAL(BaseDAL):
    """Class for basic work with Redis by connection key."""

    async def get_new_connections(self, limit: int = 100) -> List[dict[str, str]]:
        raw_data = await self.rpop_many(key=NEW_CONNECTIONS_INFO, limit=limit, json_load=False)
        # Example: token:1 --> [user_id, connection_id, meeting_id, timestamp]
        list_data = [raw.split("::") for raw in raw_data if raw]  # Ensure decoding if needed
        return [
            {"user_id": data[0], "meeting_id": data[1], "connection_id": data[2], "timestamp": data[3]}
            for data in list_data
        ]

    async def get_connection_timestamps(self, limit: int = 100) -> dict:
        # Ensure decoding if needed
        raw_data = await self.rpop_many_by_pattern(name=f"{CONNECTION_TIMESTAMP}:", limit=limit)
        return {key.split(":")[-1]: value for key, value in raw_data.items()}  # Ensure decoding if needed

    async def add_new_connection_info(self, user_id: str, meeting_id: str, connection_id: str, timestamp: str) -> None:
        await self._redis_client.lpush(NEW_CONNECTIONS_INFO, f"{user_id}::{meeting_id}::{connection_id}::{timestamp}")
        logger.info("Added new connection")

    async def add_connection_timestamp(self, connection_id: str, timestamp: str) -> None:
        await self._redis_client.lpush(f"{CONNECTION_TIMESTAMP}:{connection_id}", timestamp)
