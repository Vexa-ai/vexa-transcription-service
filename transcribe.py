
from audio.redis import *
from audio.audio import *
import io
from faster_whisper import WhisperModel

import json

import asyncio

import time


async def process(redis_client):
    try:
        _,item = await redis_client.brpop('Audio2TranscribeQueue')
        print('received')
        audio_name,client_id = item.split(':')
        audio = Audio(audio_name,redis_client)
        if await audio.get():
            print('here')
            segments, _ = model.transcribe(io.BytesIO(audio.data), beam_size=5,vad_filter=True,word_timestamps=True)
            segments = [s for s in list(segments)]
            print('done')
            transcription = [[w._asdict() for w in s.words] for s in segments]
            await Transcript(audio_name,redis_client,transcription).save()
            await redis_client.lpush(f'TranscribeReady:{audio_name}', 'Done')
    except Exception as e:
        print(e)
        await redis_client.rpush('Audio2TranscribeQueue', f'{audio_name}:{client_id}')


async def main():
    redis_client = await get_inner_redis()
    while True:
        
    # try:
    #     while True:
    #         await process(redis_client)
    # except KeyboardInterrupt:
    #     pass 
    # finally:
    #     redis_client.close()

        await process(redis_client)


if __name__ == '__main__':
    model_size = "large-v3"
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    print('model loaded')
    
    # print('test')
    asyncio.run(main())

