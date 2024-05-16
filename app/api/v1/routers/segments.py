from fastapi import APIRouter

from app.database_redis.connection import get_redis_client
from app.database_redis.dal import RedisDAL
from app.settings import settings

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get("transcribe-segments")
async def get_transcribe_segments(limit: int = 100):
    """Fetches the next set of chunks from the specified connection queue.
    The number of chunks retrieved can be specified by the num_chunks parameter.
    """
    client = RedisDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    segments = await client.get_diarize_segments(limit)
    return {"chunks": segments}


@router.get("diarize-segments")
async def get_diarize_segments(limit: int = 100):
    """Fetches the next set of chunks from the specified connection queue.
    The number of chunks retrieved can be specified by the num_chunks parameter.
    """
    client = RedisDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    segments = await client.get_transcribe_segments(limit)
    return {"chunks": segments}
