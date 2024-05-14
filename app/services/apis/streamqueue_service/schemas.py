"""Data validation for responses of StreamingQueue-service."""
from typing import Any

from pydantic import BaseModel


class Health(BaseModel):
    """StreamingQueue-service health info."""

    is_available: bool
