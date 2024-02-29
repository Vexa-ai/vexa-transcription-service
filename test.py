
from audio.redis import *
from audio.audio import *
from audio.process import *

from pathlib import Path
import json

import uuid

import pandas as pd

import asyncio
import redis.asyncio as aioredis
from dataclasses import dataclass
import numpy as np

import json
import asyncio

async def main():
    redis_inner_client = await get_inner_redis()
    redis_stream_client = await get_stream_redis()
    client_id = '851f343e-4954-4f0a-8835-9664cc91c181'
    connection_id = 'db0cc954-9ad1-4843-b77c-98bea49ce629'
    path = f'/app/testdata/{connection_id}.webm'

    start = 0
    length = 10
    end = start + length

    await writestream2file(connection_id, redis_stream_client)

    audio_slicer = await AudioSlicer.from_ffmpeg_slice(path, start, end)
    audio_data = await audio_slicer.export_data(start, end)
    audio_name = str(uuid.uuid4())
    audio = Audio(chunk_name=audio_name, redis_client=redis_inner_client, data=audio_data)
    await audio.save()

    try:
        diarization_result = await diarize(audio_data, client_id, audio_name, start)
    except KeyboardInterrupt:
        pass

    try:
        await transcribe(diarization_result, connection_id, audio_name)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    asyncio.run(main())
