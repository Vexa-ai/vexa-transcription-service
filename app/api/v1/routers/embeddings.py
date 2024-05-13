from fastapi import APIRouter, Depends

from app.database_redis.connection import get_redis_client
from app.database_redis.dal import RedisDAL
from app.settings import settings
from app.utils.token import verify_token

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.get("")
async def get_embeddings(service_token: str = Depends(verify_token), num_segments: int = 100):
    client = RedisDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    embeddings = await client.rpop_many(key="Embeddings", limit=num_segments)
    return {"embeddings": embeddings}
