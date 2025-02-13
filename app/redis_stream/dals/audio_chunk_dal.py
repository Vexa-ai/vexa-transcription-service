"""Module for basic work with Redis by audio-chunk keys."""
from typing import List, Optional, Tuple

from redis_db.dals.base import BaseDAL
from redis_db.keys import INITIAL_FEED_AUDIO


class AudioChunkDAL(BaseDAL):
    """Class for basic work with Redis by audio-chunk keys."""

    async def get_chunks_connections(self, pattern="*", min_length=1) -> List[Tuple[str, int]]:
        """
        Finds queues that match a given pattern and have a minimum number of items.
        """
        matching_queues = []
        cursor = "0"

        while cursor != 0:
            cursor, keys = await self._redis_client.scan(
                cursor,
                match=f"{INITIAL_FEED_AUDIO}:{pattern}",
                count=min_length,
            )

            for key in keys:
                length = await self._redis_client.llen(key)

                if await self._redis_client.type(key) == "list" and await self._redis_client.llen(key) >= min_length:
                    key = key.replace(f"{INITIAL_FEED_AUDIO}:", "")  # Remove the prefix
                    matching_queues.append((key, length))

        return matching_queues

    async def pop_chunks(self, connection_id: str, limit: int = 1):
        """
        Retrieves a specified number of audio chunks from this connection's queue
        in a FIFO manner using RPOP.
        """
        key = f"{INITIAL_FEED_AUDIO}:{connection_id}"
        chunks = await self.rpop_many(key, limit)
        return chunks

    async def add_chunk(self, connection_id: str, chunk: str) -> None:
        await self._redis_client.lpush(f"{INITIAL_FEED_AUDIO}:{connection_id}", chunk)
