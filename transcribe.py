
from audio.redis import *
from audio.audio import *
import io
from faster_whisper import WhisperModel

import json

import asyncio



async def process(redis_client):
    _,segment = await redis_client.brpop('TranscribeQueue')
    segment = json.loads(segment)
    audio = Audio(segment['audio_id'],redis_client)
    if await audio.get():
        print(segment['name'])
    try:
        audio_data_slicer = AudioSlicer(audio.data)
        segment_audio_data = await audio_data_slicer.export_data(segment['start'],segment['end'])

        segments, _ = model.transcribe(io.BytesIO(segment_audio_data), beam_size=5)
        data = [{'start':s.start, 'end':s.end, 'text':s.text} for s in list(segments)]
        await Transcript(segment['name'],redis_client,data).save()
        await redis_client.publish(f'TranscribeReady', segment["name"])
    except Exception as e:
        print(e)
        await redis_client.publish(f'TranscribeReady', segment["name"])


async def main():
    redis_client = await get_redis()
    while True:
        await process(redis_client)


if __name__ == '__main__':
    model_size = "large-v3"
    model = WhisperModel(model_size, device="cuda",compute_type="float16")
    

    
    while True: asyncio.run(main())

