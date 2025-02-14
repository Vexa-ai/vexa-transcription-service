"""Validators for users endpoints."""
from pydantic import BaseModel


class UserTokenCreate(BaseModel):
    """Data for user's token creation."""

    token: str
    user_id: str
    enable_status: bool


class UserSetEnableStatus(BaseModel):
    """ToDo."""

    user_id: str
    enable_status: bool


class UserResponse(BaseModel):
    """ToDo."""

    user_id: str
    enabled: bool
