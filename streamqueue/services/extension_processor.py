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
        if user_timestamp:
            audio_dt = parser.parse(datetime.utcfromtimestamp(user_timestamp).isoformat()).astimezone(UTC).isoformat()
        else:
            audio_dt: str = server_datetime.isoformat()

        logger.info(f"[PROCESS-{audio_chunk_number}] audio: {audio_dt}")
        actual_meeting_id, is_demo_meeting = self.__get_actual_meeting_id(meeting_id, connection_id, user_id)


        stream_item = {
            "chunk": chunk,
            "timestamp": audio_dt,
            "meeting_id": actual_meeting_id,
            "user_id": user_id,
            "audio_chunk_duration_sec": settings.audio_chunk_duration_sec,
            "audio_chunk_number": audio_chunk_number,
        } 
        await self.__chunk_dal.add_chunk(connection_id, json.dumps(stream_item))

    async def process_speakers_speech(
        self,
        user_id: UUID,
        connection_id: str,
        meeting_id: Optional[str],
        speakers_data: List[List[str]],  # Example: [["Speaker Name", "1001111111"], ["Speaker Name", "1011110100"], ...]
        server_datetime: datetime,
        user_timestamp: Optional[int] = None,
    ) -> None:
        if user_timestamp:
            speaker_dt = parser.parse(datetime.fromtimestamp(user_timestamp).isoformat()).astimezone(UTC).isoformat()
        else:
            speaker_dt: str = server_datetime.isoformat()

        logger.info(f"[PROCESS] speakers_speech: {speaker_dt} (user-ts: {user_timestamp})")
        actual_meeting_id, _ = self.__get_actual_meeting_id(meeting_id, connection_id, user_id)

        for speaker_data in speakers_data:
            speaker_name, meta = speaker_data
            # Note: timestamp --> dt
            speaker_item = {
                "speaker_name": speaker_name,
                "meta": meta,
                "timestamp": speaker_dt,
                "meeting_id": actual_meeting_id,
                "user_id": user_id,
                "speaker_delay_sec": settings.speaker_delay_sec,
            }
            await self.__speaker_dal.add_speaker_data(json.dumps(speaker_item))

    def __get_actual_meeting_id(self, meeting_id: Optional[str], connection_id: str, user_id: UUID) -> Tuple[str, bool]:
        """Get actual meeting id.

        Returns:
            Tuple[str, bool]: meeting_id and is_demo flag

        """

        return f"{user_id}_{connection_id}", False
