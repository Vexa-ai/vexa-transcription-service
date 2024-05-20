"""Module for basic work with radishes (get value, put value, check connection)."""
import logging
from typing import Any

from app.database_redis import keys
from app.database_redis.dals.base import BaseDAL

logger = logging.getLogger(__name__)


class SpeakerDAL(BaseDAL):
    """Class for basic work with embedding's data in Redis."""

    async def get_embeddings(self, limit: int = 100) -> Any:
        return await self.rpop_many(key=keys.SPEAKER_EMBEDDINGS, limit=limit)
