import asyncio
import logging

from app.clients.database_redis.connection import get_redis_client
from app.settings import settings
from audio.app.services.transcription.processor import Processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting transcription process")
    logger.info(f"Redis settings - Host: {settings.redis_host}, Port: {settings.redis_port}")

    try:
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port)

        processor = Processor(redis_client, logger)
        while True:
            try:
                ok = await processor.read(max_length=240)
                if ok:
                    await processor.transcribe()  # Removed unnecessary None parameter
                    await processor.find_next_seek()
            except Exception as ex:
                logger.error(f"Error in transcription loop: {ex}")
            finally:
                await processor.do_finally()
                await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
