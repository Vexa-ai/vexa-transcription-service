"""Module for basic work with Redis (get value, put value, check connection)."""
import json
import logging
from collections import defaultdict
from typing import Any

from redis.asyncio.client import Redis

from shared_lib.redis.exceptions import DataNotFoundError

logger = logging.getLogger(__name__)


class BaseDAL:
    """Class for basic work with Redis (get or put value).

    Attributes:
        _redis_client: An instance of the connection to the Redis.

    """

    def __init__(self, client: Redis):
        self._redis_client = client

    async def rpop_many_by_pattern(self, name: str, pattern: str = "*", min_length: int = 1, limit: int = 1) -> dict:
        matching_queues = defaultdict(list)
        unique_keys = set()
        cursor = "0"

        while cursor != 0:
            cursor, matched_keys = await self._redis_client.scan(cursor, match=f"{name}{pattern}", count=min_length)
            unique_keys.update(matched_keys)

        for key in unique_keys:
            for _ in range(limit):
                value = await self._redis_client.rpop(key)
                if value:
                    matching_queues[key].append(value)
                else:
                    break  # Exit if the list becomes empty before reaching num_items

        return matching_queues

    async def rpop_many(self, key: str, limit: int = 1, json_load: bool = True, raise_exception: bool = False) -> Any:
        """Retrieves a specified number of audio chunks from this connection's queue in a FIFO manner using RPOP.

        Args:
            key: Key for getting data.
            limit: ToDo.
            json_load: ToDo.
            raise_exception: ToDo.

        Returns:
            Data from redis converted to JSON.

        """
        # ToDo:
        #  if error put data in redis again
        #  if error_count > 5 put data in difference
        chunks = []

        # Continuously remove items from the right end of the list (end of the list)
        for _ in range(limit):
            chunk = await self._redis_client.rpop(key)
            if chunk:
                chunks.append(json.loads(chunk) if json_load else chunk)
            else:
                break  # Exit if the list becomes empty before reaching num_items

        if not chunks and raise_exception:
            raise DataNotFoundError(f"Data for '{key}' not found")

        return chunks
