import sys
sys.path.insert(0,'../library')

import pandas as pd
from audio.audio import AudioSlicer
import uuid
from vexa.tools import log
from vexa.redis import get_redis
from dotenv import load_dotenv
import os

import httpx
import asyncio
import os




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
from audio.redis import Audio,Transcript,Diarisation



load_dotenv()
STREAM_API_PORT = os.getenv('STREAM_API_PORT')
DATA_PATH = os.getenv('DATA_PATH')
SERVICE_TOKEN = os.getenv('SERVICE_TOKEN')







running_tasks = set()


async def get_next_chunk_start(diarization_result, length,shift):

    if len(diarization_result)>0:
        last_speech = diarization_result[-1]

        ended_silence = length - last_speech['end']
        log(ended_silence)
        if ended_silence<2:
            log('interrupted')
            return last_speech['start']+shift
        

        else:
            log('non-interrupted') 
            
            return last_speech['end']+shift



    else: return None
    
async def get_connections():

    url = f"http://host.docker.internal:{STREAM_API_PORT}/list_connections"
    params = {
            "service_token": SERVICE_TOKEN
        }
    headers = {
        "Content-Type": "application/json"
    }


    async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=2)
    
    return response.json()['connections']



async def fetch_chunks(connection_id: str, num_chunks: int):
    # Define the URL to your API endpoint
    url = f"http://host.docker.internal:{STREAM_API_PORT}/get_next_chunks/{connection_id}"
    
    # Define the parameters
    params = {
        "service_token": SERVICE_TOKEN,
        "num_chunks": num_chunks
    }

    # Use an asynchronous client from httpx
    async with httpx.AsyncClient() as client:
        try:
            # Perform the GET request
            response = await client.get(url, params=params)

            # Check if the request was successful
            if response.status_code == 200:
                if response.json() == {'message': 'No more chunks available for this connection'}:
                    print(response.json())
                    return
                else:
                    return response.json()  # Return the JSON response from the API
            else:
                return {"error": "Failed to fetch chunks", "status_code": response.status_code, "details": response.text}
        except httpx.RequestError as e:
            return {"error": "An error occurred while requesting chunks", "exception": str(e)}



async def writestream2file(connection_id):
    path = f'/audio/{connection_id}.webm'
    first_timestamp = None
    items = await  fetch_chunks(connection_id,100)

    if items:
        for item in items['chunks']:
            chunk = bytes.fromhex(item['chunk'])
            first_timestamp = item['timestamp'] if not first_timestamp else first_timestamp
            # Open the file in append mode
            with open(path, 'ab') as file:
                # Write data to the file
                file.write(chunk)
            last_timestamp = item['timestamp']
            meeting_id = item['meeting_id']
            client_id = item['client_id']
        return meeting_id, first_timestamp,last_timestamp,client_id
    
    
async def get_meeting_start(meeting_id,timestamp,redis_client):
    meeting_start = await redis_client.hget(f'Meeting:{meeting_id}','meeting_start')
    meeting_start = meeting_start if meeting_start else timestamp
    await redis_client.hset(f'Meeting:{meeting_id}','meeting_start',timestamp)
    return pd.Timestamp(meeting_start)


async def transcribe(audio_name, redis_client,client_id):
    await redis_client.lpush('Audio2TranscribeQueue', f'{audio_name}:{client_id}')
    _,done = await redis_client.brpop(f'TranscribeReady:{audio_name}',timeout=60)
    transcription =  Transcript(audio_name,redis_client)
    await transcription.get()
    return transcription.data



async def diarize(audio_name, redis_client,client_id):
    await redis_client.lpush('Audio2DiarizeQueue', f'{audio_name}:{client_id}')
    _,done = await redis_client.brpop(f'DiarizeReady:{audio_name}',timeout=60)
    diarization = Diarisation(audio_name, redis_client)
    await diarization.get()
    return diarization.data




async def process_connection(connection_id, redis_client, step=10,max_length=240):
    running_tasks.add(connection_id)
    
    path = f'/audio/{connection_id}.webm'

    start = await redis_client.rpop(f'Start:{connection_id}')
    start = float(start) if start else 0
    log('started at ',start)

    connection_output = await writestream2file(connection_id)
    if connection_output:
        meeting_id, start_timestamp,finish_timestamp, client_id = connection_output  
        meeting_start = await get_meeting_start(meeting_id,start_timestamp,redis_client)
    
    audio_slicer = await AudioSlicer.from_ffmpeg_slice(path,start,start+max_length)
    slice_duration = audio_slicer.audio.duration_seconds
    log('slice duaration ', slice_duration)

    if slice_duration > step:

        audio_data = await audio_slicer.export_data()
        audio_name = str(uuid.uuid4())
        audio = Audio(chunk_name=audio_name, redis_client=redis_client, data=audio_data)
        await audio.save()


        while True:
            try:
                log('gathering results from diarize and transcribe') 
                diarization_result, transcription_result = await asyncio.gather(
                    asyncio.wait_for(diarize   (audio_name, redis_client,client_id), timeout=60),
                    asyncio.wait_for(transcribe(audio_name, redis_client,client_id), timeout=60) 
                )
                
                await audio.delete()
            except asyncio.TimeoutError:
                log("A task has timed out")
            else:

                log('processing finished',connection_id)
                
                await redis_client.lpush(f'Segment:{connection_id}', json.dumps((diarization_result, transcription_result,start)))
                
                start_ = await get_next_chunk_start(diarization_result, slice_duration,start)
                start = start_ if start_ else start+slice_duration
                log('start')
                await redis_client.lpush(f'Start:{connection_id}', start)

                break
    else:
        await redis_client.lpush(f'Start:{connection_id}', start)


async def task_completed(connection_id,redis_client):
    if connection_id in running_tasks: 
        running_tasks.remove(connection_id)
    log(f"Task for {connection_id} completed")


async def check_and_process_connections():
    redis_client = await get_redis(host='redis',port=6379)

    while True:
        connections = await get_connections()
        connection_ids =  [c[0] for c in connections]

        for connection_id in connection_ids:
            if connection_id not in running_tasks:
                log(connection_id)
                try:
                    running_tasks.add(connection_id)
                    log('running_tasks', running_tasks)
                    task = asyncio.create_task(process_connection(connection_id, redis_client))
                    task.add_done_callback(lambda t, cid=connection_id: asyncio.create_task(task_completed(cid, redis_client)))
                except Exception as e:
                    log(f"Error processing connection {connection_id}: {e}")
                    running_tasks.remove(connection_id)

async def main():
    

    await check_and_process_connections()

if __name__ == '__main__':
    asyncio.run(main())
