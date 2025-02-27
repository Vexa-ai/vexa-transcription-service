"""Pydantic models for Redis data validation."""
from datetime import datetime
from typing import Optional, List, Any, Dict, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
    words: List[Dict[str, Union[str, float]]] = Field(
        default_factory=list,
        description="List of word information containing word text, timing, and confidence"
    )
    server_timestamp: Optional[datetime] = None  # Original server timestamp from extension
    transcription_timestamp: Optional[datetime] = None  # When the transcription was processed
    present_user_ids: List[str] = Field(default_factory=list)
    partially_present_user_ids: List[str] = Field(default_factory=list)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    @field_validator('words')
    @classmethod
    def validate_word_format(cls, v):
        """Validate that each word entry has the required fields."""
        if not isinstance(v, list):
            raise ValueError("Words must be a list")
            
        for word in v:
            if not isinstance(word, dict):
                raise ValueError("Each word must be a dictionary")
            if not all(field in word for field in ('word', 'start', 'end', 'confidence')):
                raise ValueError("Word entries must contain 'word', 'start', 'end', and 'confidence' fields")
                
        return v
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Validate that content is a non-empty string."""
        if not v or not isinstance(v, str):
            raise ValueError("Content must be a non-empty string")
        return v.strip()
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v):
        """Validate that confidence is a float between 0 and 1."""
        try:
            confidence = float(v)
            if not 0 <= confidence <= 1:
                raise ValueError("Confidence must be between 0 and 1")
            return confidence
        except (TypeError, ValueError):
            raise ValueError("Confidence must be a valid float") 