
from audio.redis import *
from audio.audio import *
#from audio.process import *

from pathlib import Path
import json

import uuid

import pandas as pd

import asyncio
import redis.asyncio as aioredis
from dataclasses import dataclass
import numpy as np

import json
import time


import subprocess
from pydub import AudioSegment
import io
from time import sleep

from dotenv import load_dotenv
import os
load_dotenv()
STREAM_REDIS_PORT = os.getenv('STREAM_REDIS_PORT')
DATA_PATH = os.getenv('DATA_PATH')




running_tasks = set()


async def get_next_chunk_start(diarization_result, length,shift):

    if len(diarization_result)>0:
        last_speech = diarization_result[-1]

        ended_silence = length - last_speech['end']
        print(ended_silence)
        if ended_silence<2:
            print('interrupted')
            return last_speech['start']+shift
        

        else:
            print('non-interrupted') 
            
            return last_speech['end']+shift



    else: return None



async def diarize(client_id, audio_name, shift, redis_inner_client):
    await redis_inner_client.lpush('Audio2DiarizeQueue', f'{audio_name}:{client_id}')
    done = await redis_inner_client.brpop(f'DiarizeReady:{audio_name}')
    diarization = Diarisation(audio_name, redis_inner_client)
    await diarization.get()
    return diarization.data

    


async def transcribe(audio_name, redis_inner_client,client_id):
    await redis_inner_client.lpush('Audio2TranscribeQueue', f'{audio_name}:{client_id}')
    _,done = await redis_inner_client.brpop(f'TranscribeReady:{audio_name}')
    transcription =  Transcript(audio_name,redis_inner_client)
    await transcription.get()
    return transcription.data




async def process_connection(connection_id, redis_stream_client, redis_inner_client, step=60,max_length=240):
    running_tasks.add(connection_id)
    
    path = f'/audio/{connection_id}.webm'

    redis_stream_client = await get_redis('host.docker.internal',STREAM_REDIS_PORT)
    redis_inner_client  = await get_redis('redis',6379)

    start = await redis_inner_client.rpop(f'Start:{connection_id}')
    start = float(start) if start else 0
    print('started at ',start)

    await writestream2file(connection_id,redis_stream_client)
    audio_slicer = await AudioSlicer.from_ffmpeg_slice(path,start,start+max_length)


    client_id = await redis_stream_client.hget('connection_client_map',connection_id)
    assert client_id is not None

    slice_duration = audio_slicer.audio.duration_seconds
    print(slice_duration)

    if slice_duration > step:

        audio_data = await audio_slicer.export_data()
        audio_name = str(uuid.uuid4())
        audio = Audio(chunk_name=audio_name, redis_client=redis_inner_client, data=audio_data)
        await audio.save()

        # print('processing',connection_id)
        # diarization_result, transcription_result = await asyncio.gather(
        #         diarize(client_id, audio_name, start,redis_inner_client),
        #         transcribe(audio_name,redis_inner_client,client_id)
        #     )
        while True:
            try:
                diarization_result, transcription_result = await asyncio.gather(
                    asyncio.wait_for(diarize(client_id, audio_name, start, redis_inner_client), timeout=60),  # Timeout after 60 seconds
                    asyncio.wait_for(transcribe(audio_name, redis_inner_client, client_id), timeout=60)  # Timeout after 60 seconds
                )
            except asyncio.TimeoutError:
                print("A task has timed out")
            else:

                print('processing finished',connection_id)
                
                await redis_inner_client.lpush(f'Segment:{connection_id}', json.dumps((diarization_result, transcription_result,start)))
                
                start_ = await get_next_chunk_start(diarization_result, slice_duration,start)
                start = start_ if start_ else start+slice_duration
                print('start')
                await redis_inner_client.lpush(f'Start:{connection_id}', start)

                break
    else:
        await redis_inner_client.lpush(f'Start:{connection_id}', start)


        await redis_inner_client.srem(f'Processfromfile',connection_id)

async def task_completed(connection_id,redis_inner_client):
    if connection_id in running_tasks: 
        running_tasks.remove(connection_id)
    print(f"Task for {connection_id} completed")


async def check_and_process_connections():
    redis_stream_client = await get_redis('host.docker.internal', port=STREAM_REDIS_PORT)
    redis_inner_client = await get_redis('redis', port=6379)

    while True:
        connections = await get_connections('initialFeed_audio', redis_stream_client)
        connection_ids = [c.replace('initialFeed_audio:', '') for c in connections]
        # files = await redis_inner_client.smembers(f'Processfromfile')
        # if len(files)>0: connection_ids.extend(list(files))  
        #else: pass
        for connection_id in connection_ids:
            if connection_id not in running_tasks:
                print(connection_id)
                try:
                    running_tasks.add(connection_id)
                    print('running_tasks', running_tasks)
                    task = asyncio.create_task(process_connection(connection_id, redis_stream_client, redis_inner_client))
                    task.add_done_callback(lambda t, cid=connection_id: asyncio.create_task(task_completed(cid, redis_inner_client)))
                except Exception as e:
                    print(f"Error processing connection {connection_id}: {e}")
                    running_tasks.remove(connection_id)
        #await asyncio.sleep(1)  # Wait for a bit before checking for new connections again

async def main():
    

    await check_and_process_connections()

if __name__ == '__main__':
    asyncio.run(main())

