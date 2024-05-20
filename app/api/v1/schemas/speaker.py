"""Data validation for /speakers endpoints."""
from typing import Any

from pydantic import BaseModel


class SpeakerEmbeddings(BaseModel):
    """Embedding data."""

    speaker_id: str
    user_id: int
    embedding_data: Any
