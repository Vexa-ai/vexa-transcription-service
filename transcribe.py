
from audio.redis import *
from audio.audio import *
import io
from faster_whisper import WhisperModel

import json

import asyncio

import time


async def process(redis_client):
    _,segment = await redis_client.brpop('TranscribeQueue')
    await redis_client.lpush('REceived', str(time.time()))
    print(f'transcribe job received {time.time()}')
    segment = json.loads(segment)
    audio = Audio(segment['audio_id'],redis_client)
    if await audio.get():
        print('got')
        print(segment['name'])
    try:
        audio_data_slicer = AudioSlicer(audio.data)
        segment_audio_data = await audio_data_slicer.export_data(segment['start'],segment['end'])
        print('transcribe job started')
        
        segments, _ = model.transcribe(io.BytesIO(segment_audio_data), beam_size=5,vad_filter=True)
        start_time = time.time()
        data = [{'start':s.start, 'end':s.end, 'text':s.text} for s in list(segments)]
        await Transcript(segment['name'],redis_client,data).save()
        finish_time = time.time()
        print(finish_time-start_time)
        print('transcribe job done')
        print('finished')

        
    except Exception as e:
        print(e)
    finally:
        await redis_client.lpush(f'TranscribeReady:{segment["name"]}', 'Done')
        
# async def process(redis_client):
#     print('1')
#    # _,segment = await redis_client.brpop('TranscribeQueue')
#     _,segment = await redis_client.brpop('TranscribeQueue')
#     await redis_client.lpush('REceived', str(time.time()))


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
    model = WhisperModel(model_size,compute_type="float16")
    print('model loaded')
    
    # print('test')
    asyncio.run(main())

