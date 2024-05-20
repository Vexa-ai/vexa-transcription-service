"""Data validation for /speakers endpoints."""
from typing import Any, List

from pydantic import BaseModel


class Segment(BaseModel):
    """Diarizer/Transcriber segment data."""

    meeting_id: str
    data: List[Any]
