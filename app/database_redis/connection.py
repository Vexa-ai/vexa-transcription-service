"""Redis connection."""
from typing import Optional

from redis.asyncio.client import Redis
from redis.exceptions import ConnectionError

from app.database_redis.exceptions import RedisConnectionError


async def get_redis_client(host: str, port: int, password: Optional[str] = None) -> Redis:
    """ToDo."""
    try:
        # import redis.asyncio as aioredis
        # redis_client = await aioredis.from_url(f"redis://{host}:{port}/0", decode_responses=True)
        redis_client = Redis(host=host, port=port, password=password, decode_responses=True)
        await redis_client.ping()

    except ConnectionError:
        raise RedisConnectionError("Redis connection error. Check if the connection configuration is correct")

    return redis_client
