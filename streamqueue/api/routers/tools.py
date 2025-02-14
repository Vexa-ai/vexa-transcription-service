from typing import List

from fastapi import APIRouter

from api.schemas import AudioChunkInfo, SpeakerInfo, AddTokenRequest
from redis_db.shared_lib..connection import get_redis_client
from redis_db.shared_lib..dals.audio_chunk_dal import AudioChunkDAL
from redis_db.shared_lib..dals.speaker_dal import SpeakerDAL
from redis_db.shared_lib..dals.admin_dal import AdminDAL
from settings import settings

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/flush-cache")
async def flush_cache():
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    await client.flushdb()
    return {"message": "cache flushed successfully"}


@router.post("/flush-admin-cache")
async def flush_admin_cache():
    admin_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password, db=1)
    await admin_client.flushdb()
    return {"message": "admin cache flushed successfully"}


@router.post("/add-token")
async def add_token(request: AddTokenRequest):
    """Add a new user token to Redis."""
    admin_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password, db=1)
    admin_dal = AdminDAL(admin_client)
    
    await admin_dal.add_token(request.token, request.user_id, request.enable)
    return {"message": "Token added successfully"}
