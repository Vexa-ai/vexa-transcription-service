"""Redis connection."""
from typing import Optional, Union

from redis.asyncio.client import Redis
from redis_db.exceptions import RedisConnectionError
from redis.exceptions import ConnectionError

async def get_redis_client(host: str, port: int, password: Optional[str] = None, db: Union[str, int] = 0) -> Redis: #database 0 will be for streamqueue
    """ToDo."""
    try:
        # import redis.asyncio as aioredis
        # redis_client = await aioredis.from_url(f"redis://{host}:{port}/0", decode_responses=True)
        redis_client = Redis(host=host, port=port, password=password, db=db, decode_responses=True)
        await redis_client.ping()

    except ConnectionError:
        raise RedisConnectionError("Redis connection error. Check if the connection configuration is correct")

    return redis_client
