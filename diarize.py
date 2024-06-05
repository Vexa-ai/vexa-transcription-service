import asyncio
import logging
from app.settings import settings

from processor import Processor
from app.database_redis.connection import get_redis_client
from pyannote.audio import Pipeline
import torch
from qdrant_client import QdrantClient, models

async def main():
    # Configure logger
    logger = logging.getLogger("diarize")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info("Running diarize loop...")

    redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    

    pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token="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",
        )
    pipeline.to(torch.device("cuda"))
    qdrant_client = QdrantClient("qdrant", timeout=10)

    diarizer = Processor('diarizer', redis_client, logger)
    while True:
       # try:
        ok = await diarizer.read(max_length=240)
        if ok:
            await diarizer.diarize(pipeline,qdrant_client)
            await diarizer.find_next_seek()
        # except Exception as ex:
        #     logger.error(ex)
        # finally:
        await diarizer.do_finally()
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())