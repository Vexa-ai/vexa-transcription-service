"""Module for basic work with radishes (get value, put value, check connection)."""
import logging

from app.clients.database_redis import keys
from app.clients.database_redis.dals.base import BaseDAL

logger = logging.getLogger(__name__)


class SegmentDAL(BaseDAL):
    """Class for basic work with segment's data in Redis."""


    async def get_transcribe_segments(self, limit: int = 100) -> dict:
        transcribe_segments = await self.rpop_many_by_pattern(name=keys.SEGMENTS_TRANSCRIBE, limit=limit)
        transcribe_data = {key.split(":")[-1]: value for key, value in transcribe_segments.items()}
        return transcribe_data
