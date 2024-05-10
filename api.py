from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
import uuid
from typing import Optional


import redis.asyncio as aioredis

from typing import Annotated
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

import httpx
import asyncio
import sys
sys.path.insert(0,'../library')
from vexa.redis import get_redis,pop_items
from vexa.tools import log



app = FastAPI()

origins = [
    "http://*",
    "https://*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from dotenv import load_dotenv
load_dotenv()

AUDIO_API_PORT = os.getenv("AUDIO_API_PORT")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN")

print('AUDIO_API_PORT',AUDIO_API_PORT)


@app.on_event("startup")
async def startup_event():
    global redis_client

    redis_client = await get_redis(host='redis',port=6379)
    
    
async def check_redis():
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis client not initialized")
    

async def check_service_token(service_token):

    expected_service_token = os.getenv("SERVICE_TOKEN")
    if service_token != expected_service_token:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid service token")
    


@app.get("/get_segments")
async def get_next_segments(service_token: str, num_segments: int = 100):
    """
    Fetches the next set of segments from the specified connection queue.
    The number of segments retrieved can be specified by the num_segments parameter.
    """
    await check_redis()
    await check_service_token(service_token)

    segments = await pop_items(redis_client, 'Segments',num_items=num_segments)
    #log('get_next_segments' ,len(segments))
    if segments:
        return {"segments": segments}
    else:
        return {"message": "No more segments available"}
    
@app.post("/flush_cache")
async def flush_cache(): #
    await check_redis()
  #  await check_service_token(service_token)

    await redis_client.flushdb()
    return {"message": "cache flushed successfully"}



# uvicorn api:app --host 0.0.0.0 --port 8002 --reload