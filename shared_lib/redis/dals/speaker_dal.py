"""Module for basic work with Redis by speaker keys."""
from typing import List

from shared_lib.redis.dals.base import BaseDAL
from shared_lib.redis.keys import SPEAKER_DATA
from shared_lib.redis.models import SpeakerDataModel


class SpeakerDAL(BaseDAL):
    """Class for basic work with Redis by speaker keys."""

    async def add_speaker_data(self, speaker_data: dict) -> None:
        # Validate the data
        speaker_model = SpeakerDataModel(**speaker_data)
        await self._redis_client.lpush(
            SPEAKER_DATA, 
            speaker_model.model_dump_json()
        )

    async def pop_chunks(self, limit: int = 1) -> List[dict]:
        return await self.rpop_many(SPEAKER_DATA, limit, json_load=True)
