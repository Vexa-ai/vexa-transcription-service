"""Data validation for /speakers endpoints."""
from typing import Any, List

from pydantic import BaseModel


class SpeakerEmbeddings(BaseModel):
    """Embedding data."""

    speaker_id: str
    user_id: str
    embedding_data: List[Any]
