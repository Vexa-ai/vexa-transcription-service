from fastapi import FastAPI, BackgroundTasks

from audio.redis import *
from audio.audio import *

import pandas as pd
import numpy as np
import json

app = FastAPI()

async def get_next_chunk_start(diarization_result, length):
    if len(diarization_result)>0:
        last_speech = diarization_result[-1]

        ended_silence = length - last_speech['end']
        print(ended_silence)
        if ended_silence<1:
            print('interrupted')
            return last_speech['conv_start']
        

        else:
            print('non-interrupted') 
            return last_speech['conv_end']



    else: return None


async def diarize(client_id, audio_name, shift):
    redis_inner_client = await get_inner_redis()
    await redis_inner_client.lpush('Audio2DiarizeQueue', f'{audio_name}:{client_id}')
    done = await redis_inner_client.brpop(f'DiarizeReady:{audio_name}')
    diarization = Diarisation(audio_name, redis_inner_client)
    await diarization.get()
    df = pd.DataFrame(diarization.data)
    if len(df)>0:
        df['silence'] = df['start']-df['end'].shift()
        df['speaker_change'] = df['speaker'] != df['speaker'].shift()
        df['len'] = df['end'] - df['start']
        df = df[df['len'] > 0.5]
        df['speaker_change'] = np.where(df['silence']>2,True,df['speaker_change'])

        df['speaker_change'] = df['speaker_change'].cumsum()
        df = df.groupby('speaker_change').agg({'speaker': 'first', 'start': 'first', 'end': 'last'})
        df['conv_start'] = df['start'] + shift
        df['conv_end'] = df['end'] + shift
        return df.to_dict('records')
    else: return df

async def transcribe(diarization_result,connection_id,audio_name):
    redis_inner_client = await get_inner_redis()
    for segment in diarization_result:
        segment['connection_id'] = connection_id
        segment['name'] = str(uuid.uuid4())
        segment['audio_id'] = audio_name
        await redis_inner_client.lpush('TranscribeQueue', json.dumps(segment))
        done = await redis_inner_client.brpop(f'TranscribeReady:{segment["name"]}')
        print('done')
        transcription = Transcript(segment["name"],redis_inner_client)
        await transcription.get()
        segment['transcription'] = transcription.data
        await redis_inner_client.lpush(f'Segment:{connection_id}', json.dumps(segment))



async def fetch_connection_queue_keys(master_set_key: str) -> list:
    """Fetch the keys of all active connection queues from a master set."""
    redis_stream_client = await get_stream_redis()
    connection_queue_keys = await get_connections('initialFeed_audio',redis_stream_client)
    await redis_stream_client.close()
    return connection_queue_keys




async def process_connection_queue(connection_id: str):
    """Process items from a specific connection queue."""
    redis_stream_client = await get_stream_redis()
    on_start = True
    start = 0
    length = 60
    
    while True:
        await writestream2file(connection_id,redis_stream_client)

        if on_start:  audio_slicer = await AudioSlicer.from_file(path,format = 'webm')
        else       :  audio_slicer = await AudioSlicer.from_ffmpeg_slice(path,start,start+600000)

        slice_duration = audio_slicer.audio.duration_seconds
        if slice_duration > length:

            audio_data = await audio_slicer.export_data()
            audio_name = str(uuid.uuid4())
            audio = Audio(chunk_name=audio_name, redis_client=redis_inner_client, data=audio_data)
            await audio.save()

            print('waiting diarize')
            diarization_result = await diarize(client_id,audio_name,start)
            print('waiting transcribe')
            await transcribe(diarization_result,connection_id,audio_name)
            start_ = await get_next_chunk_start(diarization_result,slice_duration)
            start = start_ if start_ else start+length

        elif slice_duration > length and length == 0:
            break
        
        else:
            length = 0
        

        
    await redis_stream_client.close()  # Close the connection after processing the queue

@app.post("/process-connections/")
async def process_connections(background_tasks: BackgroundTasks, master_set_key: str = "connection_queue_keys"):
    """Endpoint to start processing all connection queues listed in the master set."""
    connection_queue_keys = await fetch_connection_queue_keys(master_set_key)
    for queue_key in connection_queue_keys:
        # Schedule each queue for processing as a background task
        background_tasks.add_task(process_connection_queue, queue_key)
    
    return {"message": f"Started processing {len(connection_queue_keys)} connection queues."}
