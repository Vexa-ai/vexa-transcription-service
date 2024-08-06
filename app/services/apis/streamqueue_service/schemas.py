"""Data validation for responses of StreamingQueue-service."""
from pydantic import BaseModel


class Health(BaseModel):
    """StreamingQueue-service health info."""

    is_available: bool


class ExistingConnectionInfo(BaseModel):
    """Connection info received from the extension."""

    connection_id: str
    amount: int


class AudioChunkInfo(BaseModel):
    """Audio chink data."""

    meeting_id: str
    user_id: str
    chunk: str
    timestamp: str
