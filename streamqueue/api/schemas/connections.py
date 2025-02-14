from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ExistingConnectionInfo(BaseModel):
    """Connection info received from the extension."""

    connection_id: str
    amount: int


class NewConnectionInfo(BaseModel):
    """Connection info received from the extension."""

    user_id: str
    meeting_id: str
    connection_id: str
    timestamp: datetime


class ConnectionTimestampsInfo(BaseModel):
    """Connection info received from the extension."""

    connection_id: str
    timestamps: List[Optional[str]]
