"""Redis connection."""
from typing import Optional
import logging

from redis.asyncio.client import Redis
from redis.exceptions import ConnectionError

from app.redis_transcribe.exceptions import RedisConnectionError

logger = logging.getLogger(__name__)

async def get_redis_client(host: str, port: int, password: Optional[str] = None, db: int = 0) -> Redis:
    """Create Redis client connection with detailed logging."""
    logger.info(f"Attempting Redis connection to {host}:{port}")
    if password:
        logger.info("Redis password is configured")
    else:
        logger.info("No Redis password configured")

    try:
        logger.debug("Initializing Redis client")
        redis_client = Redis(host=host, port=port, password=password, db=db, decode_responses=True)
        
        logger.debug("Attempting to ping Redis server")
        await redis_client.ping()
        logger.info("Successfully connected to Redis server")

    except ConnectionError as e:
        logger.error(f"Redis connection error: {str(e)}")
        logger.error(f"Connection details - Host: {host}, Port: {port}")
        raise RedisConnectionError("Redis connection error. Check if the connection configuration is correct")
    except Exception as e:
        logger.error(f"Unexpected error during Redis connection: {str(e)}")
        raise

    return redis_client
