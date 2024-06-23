import asyncio
import logging

from faster_whisper import WhisperModel

from app.database_redis.connection import get_redis_client
from app.settings import settings
from processor import Processor


async def main():
    # Configure logger
    logger = logging.getLogger("transcribe")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info("Running transcribe loop...")

    redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)

    model_size = "large-v3"
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    transcriber = Processor("transcriber", redis_client, logger)
    while True:

        ok = await transcriber.read(max_length=10)
        if ok:
            await transcriber.transcribe(model)
            await transcriber.find_next_seek()

        await transcriber.do_finally()
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
