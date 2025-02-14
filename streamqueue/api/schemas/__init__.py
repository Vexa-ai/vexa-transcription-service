from api.schemas.connections import ConnectionTimestampsInfo, ExistingConnectionInfo, NewConnectionInfo
from api.schemas.extension import TokenValidationResult
from api.schemas.tools import AudioChunkInfo, SpeakerInfo
from api.schemas.user import UserResponse, UserSetEnableStatus, UserTokenCreate
from pydantic import BaseModel

__all__ = [
    "ConnectionTimestampsInfo",
    "UserResponse",
    "ExistingConnectionInfo",
    "NewConnectionInfo",
    "TokenValidationResult",
    "AudioChunkInfo",
    "SpeakerInfo",
    "UserSetEnableStatus",
    "UserTokenCreate",
]

class TokenValidationResult(BaseModel):
    is_valid: bool

class AddTokenRequest(BaseModel):
    token: str
    user_id: str
    enable: bool = True
