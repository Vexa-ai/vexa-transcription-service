from fastapi import APIRouter, Depends

from app.database_redis.connection import get_redis_client
from app.database_redis.dal import RedisDAL
from app.settings import settings
from app.utils.token import verify_token

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get("")
async def get_segments(service_token: str = Depends(verify_token), num_segments: int = 100):
    """Fetches the next set of chunks from the specified connection queue.
    The number of chunks retrieved can be specified by the num_chunks parameter.
    """
    client = RedisDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    segments = await client.rpop_many(key="Segments", limit=num_segments)
    return {"chunks": segments}
