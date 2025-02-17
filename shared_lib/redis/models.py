"""Pydantic models for Redis data validation."""
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID

from pydantic import BaseModel, Field


class AudioChunkModel(BaseModel):
    """Model for audio chunk data validation."""
    chunk: str
    user_timestamp: str
    server_timestamp: str
    meeting_id: Optional[str] = None
    user_id: UUID
    audio_chunk_duration_sec: float
    audio_chunk_number: int


class SpeakerDataModel(BaseModel):
    """Model for speaker data validation."""
    speaker_name: str
    meta: str
    user_timestamp: str
    server_timestamp: str
    meeting_id: Optional[str] = None
    user_id: UUID
    speaker_delay_sec: float


class TranscriptSegmentModel(BaseModel):
    """Model for individual transcript segments."""
    content: str
    start_timestamp: datetime
    end_timestamp: datetime
    speaker: Optional[str] = None
    confidence: float
    segment_id: int
    meeting_id: Optional[str] = None
    words: Optional[List[List[Any]]] = None
    server_timestamp: Optional[datetime] = None  # Original server timestamp from extension
    transcription_timestamp: Optional[datetime] = None  # When the transcription was processed 