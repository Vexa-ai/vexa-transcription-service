import io
from faster_whisper import WhisperModel

from app.services.audio.redis import Audio, Transcript
from app.settings import settings
import asyncio
from app.database_redis.connection import get_redis_client

import logging

logger = logging.getLogger(__name__)


async def process(redis_client) -> None:
    try:
        _, item = await redis_client.brpop('Audio2TranscribeQueue')
        logger.info('received transcribe item')
        audio_name, client_id = item.split(':')

    except Exception as ex:
        logger.exception(ex)
        return

    try:
        audio = Audio(audio_name, redis_client)

        if await audio.get():
            segments, _ = model.transcribe(io.BytesIO(audio.data), beam_size=5, vad_filter=True, word_timestamps=True)
            segments = [s for s in list(segments)]
            logger.info('done')
            transcription = [[w._asdict() for w in s.words] for s in segments]
            await Transcript(audio_name, redis_client, transcription).save()
            await redis_client.lpush(f'TranscribeReady:{audio_name}', 'Done')
            logger.info('done')

    except Exception as ex:
        logger.exception(ex)
        await redis_client.rpush('Audio2TranscribeQueue', f'{audio_name}:{client_id}')


async def main():
    redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)

    while True:
        await asyncio.sleep(0.1)
        await process(redis_client)


if __name__ == '__main__':
    model_size = "large-v3"
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    logger.info('Model loaded')
    asyncio.run(main())
