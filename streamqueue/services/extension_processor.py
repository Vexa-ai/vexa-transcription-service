"""Processor of Chrome extension """
import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from dateutil import parser
from dateutil.tz import UTC
from redis.asyncio import Redis

from shared_lib.redis.dals.audio_chunk_dal import AudioChunkDAL

from shared_lib.redis.dals.speaker_dal import SpeakerDAL
from streamqueue.settings import settings
from shared_lib.redis.models import AudioChunkModel, SpeakerDataModel

logger = logging.getLogger(__name__)


class ExtensionProcessor:
    def __init__(self, redis_connection: Redis):
        self.__chunk_dal = AudioChunkDAL(redis_connection)
        self.__speaker_dal = SpeakerDAL(redis_connection)


    async def process_audio(
        self,
        user_id: UUID,
        connection_id: str,
        meeting_id: Optional[str],
        audio_chunk_number: int,
        chunk: str,
        server_datetime: datetime,
        user_timestamp: Optional[int] = None,
    ) -> None:
        user_timestamp = parser.parse(datetime.utcfromtimestamp(user_timestamp).isoformat()).astimezone(UTC).isoformat()
        server_timestamp: str = server_datetime.isoformat()

        logger.info(f"[PROCESS-{audio_chunk_number}] audio: {server_datetime}")

        # Validate the data using Pydantic model
        stream_item = AudioChunkModel(
            chunk=chunk,
            user_timestamp=user_timestamp,
            server_timestamp=server_timestamp,
            meeting_id=meeting_id,
            user_id=user_id,
            audio_chunk_duration_sec=settings.audio_chunk_duration_sec,
            audio_chunk_number=audio_chunk_number,
        )
        await self.__chunk_dal.add_chunk(connection_id, stream_item.model_dump())

    async def process_speakers_speech(
        self,
        user_id: UUID,
        connection_id: str,
        meeting_id: Optional[str],
        speakers_data: List[List[str]],  # Example: [["Speaker Name", "1001111111"], ["Speaker Name", "1011110100"], ...]
        server_datetime: datetime,
        user_timestamp: Optional[int] = None,
    ) -> None:

        user_timestamp = parser.parse(datetime.fromtimestamp(user_timestamp).isoformat()).astimezone(UTC).isoformat()
        server_timestamp: str = server_datetime.isoformat()

        logger.info(f"[PROCESS] speakers_speech: {user_timestamp} (user-ts: {user_timestamp})")

        for speaker_data in speakers_data:
            speaker_name, meta = speaker_data
            # Validate the data using Pydantic model
            speaker_item = SpeakerDataModel(
                speaker_name=speaker_name,
                meta=meta,
                user_timestamp=user_timestamp,
                server_timestamp=server_timestamp,
                meeting_id=meeting_id,
                user_id=user_id,
                speaker_delay_sec=settings.speaker_delay_sec,
            )
            await self.__speaker_dal.add_speaker_data(speaker_item.model_dump())

