from fastapi import APIRouter

from app.database_redis.connection import get_redis_client
from app.settings import settings

router = APIRouter(prefix="tools", tags=["tools"])


@router.post("/flush_cache")
async def flush_cache():
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    await client.flushdb()
    return {"message": "cache flushed successfully"}
