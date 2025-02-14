"""Validators for tools endpoints."""
from pydantic import BaseModel


class AudioChunkInfo(BaseModel):
    """Audio chink data."""

    meeting_id: str
    user_id: str
    chunk: str
    timestamp: str
    audio_chunk_duration_sec: int


class SpeakerInfo(BaseModel):
    """Speaker data."""

    meeting_id: str
    user_id: str
    speaker_name: str
    meta: str
    timestamp: str
    speaker_delay_sec: int
