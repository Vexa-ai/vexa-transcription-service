from fastapi import APIRouter

from app.database_redis.connection import get_redis_client
from app.database_redis.dal import RedisDAL
from app.settings import settings

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.get("")
async def get_embeddings(limit: int = 100):
    client = RedisDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    embeddings = await client.get_embeddings(limit)
    return {"embeddings": embeddings}
