
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

client_id = '851f343e-4954-4f0a-8835-9664cc91c181'
import subprocess
from pydub import AudioSegment
import io
from time import sleep

from audio.redis import Transcript

running_tasks = set()



async def get_next_chunk_start(redis_inner_client, audio_name, length,shift):
    diarization = Diarisation(audio_name, redis_inner_client)
    await diarization.get()
    diarization_result = diarization.data

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
    df = pd.DataFrame(diarization.data)
    df['len'] = df['end'] - df['start']
    df = df[df['len']>0.7]

    if len(df)>0:
        expanded_df = pd.DataFrame(columns=['speaker', 'time'])
        for index, row in df.iterrows():
            time_range = np.arange(row['start'] * 100, row['end'] * 100, 1).astype(int)

            temp_df = pd.DataFrame({
                'speaker': row['speaker'],
                'time': time_range
            })
            expanded_df = pd.concat([expanded_df, temp_df], ignore_index=True)
        expanded_df['time'] = (expanded_df['time'] / 100.0).astype('float')
        expanded_df['conv_time'] = (expanded_df['time'] + shift).astype('float')

        return expanded_df.sort_values("time")
    


async def transcribe(audio_name, redis_inner_client):
    await redis_inner_client.lpush('Audio2TranscribeQueue', f'{audio_name}:{client_id}')
    _,done = await redis_inner_client.brpop(f'TranscribeReady:{audio_name}')
    transcription =  Transcript(audio_name,redis_inner_client)
    await transcription.get()
    df =  pd.concat([pd.DataFrame(t) for t in transcription.data])


    df['start'] = df['start'].astype('float')
    return df.sort_values("start")


async def process_connection(connection_id, redis_stream_client, redis_inner_client, step=20,max_length=600):
    path = f'/app/testdata/{connection_id}.webm'

    redis_stream_client = await get_stream_redis()
    redis_inner_client = await get_inner_redis()

    start = await redis_inner_client.rpop(f'Start:{connection_id}')
    start = float(start) if start else 0
    print('started at ',start)

    await writestream2file(connection_id,redis_stream_client)
    audio_slicer = await AudioSlicer.from_ffmpeg_slice(path,start,max_length)

    slice_duration = audio_slicer.audio.duration_seconds
    print(slice_duration)

    if slice_duration > step:

        audio_data = await audio_slicer.export_data()
        audio_name = str(uuid.uuid4())
        audio = Audio(chunk_name=audio_name, redis_client=redis_inner_client, data=audio_data)
        await audio.save()

        diarization_result, transcription_result = await asyncio.gather(
                diarize(client_id, audio_name, start,redis_inner_client),
                transcribe(audio_name,redis_inner_client)
            )

        df = pd.merge_asof(transcription_result,diarization_result,left_on = 'start',right_on='time',direction='nearest')
        df['speaker_change'] = df['speaker'] != df['speaker'].shift()
        df['silence'] = df['start']-df['end'].shift()
        df['speaker_change'] = np.where(df['silence']>2,True,df['speaker_change'])
        df['speaker_change'] = df['speaker_change'].cumsum()
        df = df.groupby('speaker_change').agg({'speaker': 'first', 'start': 'first', 'end': 'last'}).join(df.groupby('speaker_change').apply(lambda x:''.join(x['word'])).to_frame('text'))
        df['len'] = df['end'] - df['start']
        df['speaker'] = df['speaker'].fillna(method='ffill').fillna(method='bfill')
        df['conv_start'] = df['start']+start
        df['conv_end'] = df['end']+start

        start_ = await get_next_chunk_start(redis_inner_client, audio_name, slice_duration,start)
        start = start_ if start_ else start+slice_duration
        await redis_inner_client.lpush(f'Start:{connection_id}', start)


        await redis_inner_client.lpush(f'Segment:{connection_id}', json.dumps(df.to_dict(orient='records')))

    else:
        await redis_inner_client.lpush(f'Start:{connection_id}', start)

    running_tasks.remove(connection_id)

def task_completed(task, connection_id):
    running_tasks.remove(connection_id)
    print(f"Task for {connection_id} completed")



async def check_and_process_connections():
    redis_stream_client = await get_stream_redis()
    redis_inner_client = await get_inner_redis()

    while True:
        connections = await get_connections('initialFeed_audio', redis_stream_client)
        connection_ids = [c.replace('initialFeed_audio:', '') for c in connections]
        for connection_id in connection_ids:
            if connection_id not in running_tasks:
                running_tasks.add(connection_id)
                task = asyncio.create_task(process_connection(connection_id, redis_stream_client, redis_inner_client))
                task.add_done_callback(lambda t, cid=connection_id: task_completed(t, cid))
        #await asyncio.sleep(1)  # Wait for a bit before checking for new connections again

async def main():
    

    await check_and_process_connections()

if __name__ == '__main__':
    asyncio.run(main())

