from fastapi import APIRouter

from app.database_redis.connection import get_redis_client
from app.settings import settings

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/flush-cache")
async def flush_cache():
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    await client.flushdb()
    return {"message": "cache flushed successfully"}


@router.get("/diarization-queue-size")
async def get_diarization_queue_size():
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    queue_size = await client.llen("diarize:todo")
    return {"amount": queue_size}


@router.get("/transcribing-queue-size")
async def get_transcribing_queue_size():
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    queue_size = await client.llen("transcribe:todo")
    return {"amount": queue_size}
