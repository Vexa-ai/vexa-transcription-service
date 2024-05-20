"""Module for basic work with radishes (get value, put value, check connection)."""
import logging
from collections import defaultdict
from typing import Any

from app.database_redis import keys
from app.database_redis.dals.base import BaseDAL

logger = logging.getLogger(__name__)


class SegmentDAL(BaseDAL):
    """Class for basic work with segment's data in Redis."""

    async def get_all_segments(self, limit: int = 100) -> dict:
        all_segments_data = defaultdict(list)
        meeting_keys = set()

        diarize_segments = await self.get_diarize_segments(limit)
        diarize_data = {key.split(":")[-1]: value for key, value in diarize_segments.items()}
        meeting_keys.add([key for key in diarize_data.keys()])

        transcribe_segments = await self.get_transcribe_segments(limit)
        transcribe_data = {key.split(":")[-1]: value for key, value in transcribe_segments.items()}
        meeting_keys.add([key for key in transcribe_data.keys()])

        # Merge dicts
        for key in meeting_keys:
            if diarize_value := diarize_data.get(key):
                all_segments_data[key].append(diarize_value)

            if transcribe_value := transcribe_data.get(key):
                all_segments_data[key].append(transcribe_value)

        return all_segments_data

    async def get_diarize_segments(self, limit: int = 100) -> Any:
        return await self.rpop_many_by_pattern(name=keys.SEGMENTS_DIARIZE)

    async def get_transcribe_segments(self, limit: int = 100) -> Any:
        return await self.rpop_many_by_pattern(name=keys.SEGMENTS_TRANSCRIBE)
