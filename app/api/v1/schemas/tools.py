from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DiarizationStart(BaseModel):
    user_id: UUID
    meeting_id: str
    connection_id: str
    diarizer_last_updated_timestamp: datetime
    start_timestamp: datetime
    end_timestamp: datetime


class TranscribingStart(BaseModel):
    user_id: UUID
    meeting_id: str
    connection_id: str
    transcriber_last_updated_timestamp: datetime
    start_timestamp: datetime
    end_timestamp: datetime
