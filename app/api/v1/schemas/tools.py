from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DiarizationStart(BaseModel):
    user_id: UUID
    meeting_id: str
    connection_id: str
    start_timestamp: datetime
    end_timestamp: datetime


class TranscribingStart(BaseModel):
    user_id: UUID
    meeting_id: str
    connection_id: str
    start_timestamp: datetime
    end_timestamp: datetime
