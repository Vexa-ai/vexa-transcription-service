"""Module for basic work with radishes (get value, put value, check connection)."""
import json
import logging
from typing import Any

from redis.asyncio.client import Redis

from app.database_redis.exceptions import DataNotFoundError
from app.database_redis import keys

logger = logging.getLogger(__name__)


class RedisDAL:
    """Class for basic work with Redis (get or put value).

    Attributes:
        __redis_client: An instance of the connection to the Redis.

    """

    def __init__(self, client: Redis):
        self.__redis_client = client

    async def get_embeddings(self, limit: int = 100) -> Any:
        return await self.rpop_many(key=keys.EMBEDDINGS, limit=limit)

    async def get_segments(self, limit: int = 100) -> Any:
        return await self.rpop_many(key=keys.SEGMENTS, limit=limit)

    async def rpop_many(self, key: str, limit: int = 1, raise_exception: bool = False) -> Any:
        """Retrieves a specified number of audio chunks from this connection's queue in a FIFO manner using RPOP.

        Args:
            key: Key for getting data.
            limit: ToDo.
            raise_exception: ToDo.

        Returns:
            Data from redis converted to JSON.

        """
        # ToDo:
        #  if error put data in redis again
        #  if error_count > 5 put data in difference
        chunks = []

        for _ in range(limit):
            chunk = await self.__redis_client.rpop(key)
            if chunk:
                chunks.append(json.loads(chunk))
            else:
                break

        if chunks:
            return chunks

        if raise_exception:
            raise DataNotFoundError(f"Data for '{key}' not found")
