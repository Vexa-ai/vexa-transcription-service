"""Module for checking the status (health) of the service."""
import logging

from app.clients.database_redis.connection import get_redis_client
from app.clients.database_redis.exceptions import RedisConnectionError
from app.clients.apis.streamqueue_service.client import StreamQueueServiceAPI
from app.clients.apis.streamqueue_service.exceptions import StreamQueueServiceBaseError
from app.services.health.enums import Entry
from app.services.health.schemas import Health, HealthCommon
from app.settings import settings

logger = logging.getLogger(__name__)


async def check_redis_health_status() -> bool:
    """Check redis connection (ping redis).

    Returns:
        - True: service is available.
        - False: service is not available.

    """
    logger.info("Check redis..")

    try:
        await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        return True

    except RedisConnectionError as ex:
        logger.error(f"Cannot connect to the redis ({settings.redis_host}: {settings.redis_port}). Exception: {ex}")
        return False


async def check_stream_queue_service_health_status() -> bool:
    """Check api endpoint response status == 200.

    Returns:
        healthy or not.

    """
    logger.info(f"Check StreamQueueService API {settings.stream_queue_service_health}..")

    try:
        request_sender = StreamQueueServiceAPI()
        return await request_sender.health()

    except StreamQueueServiceBaseError as ex:
        logger.error(f"Cannot connect to the service by URL: {settings.stream_queue_service_health}. Exception: {ex}")
        return False


async def health_check() -> HealthCommon:
    """Get the health status of the current service and dependencies (redis/external services).

    Returns:
        Dictionary of external dependencies with their statuses.

    """
    entries_status = {
        Entry.SELF: Health(is_available=True),
        Entry.REDIS: Health(is_available=await check_redis_health_status()),
        Entry.STREAM_QUEUE_SERVICE: Health(is_available=await check_stream_queue_service_health_status()),
    }
    entries_statuses = [entry_status.is_available for entry_status in entries_status.values()]
    return HealthCommon(is_available=False if False in entries_statuses else True, entries=entries_status)
