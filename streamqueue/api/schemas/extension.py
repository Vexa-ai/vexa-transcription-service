from enum import Enum

from pydantic import BaseModel


class SourceType(str, Enum):
    GOOGLE_MEET = "google_meet"
    YOUTUBE = "youtube"
    ZOOM = "zoom"


class TokenValidationResult(BaseModel):
    is_valid: bool
