# %% ../nbs/00_redis.ipynb 3
import redis.asyncio as aioredis
from pydantic import BaseModel
from typing import Optional,Union,List, Literal
from dataclasses import dataclass
import redis
import json

@dataclass
class Data:
    chunk_name:str
    key:Literal['audio','transcription','diarisation']
    redis_client: redis.client.Redis
    data: Union[List, bytes]=None
    

    async def save(self):
            if isinstance(self.data, bytes): 
                data = self.data.hex()
            else: 
                data = json.dumps(self.data)
            await self.redis_client.hset(self.chunk_name, self.key, data)

    async def get(self):
        data = await self.redis_client.hget(self.chunk_name, self.key)
        if data:
            if self.key == 'audio': 
                self.data = bytes.fromhex(data)
            else: 
                self.data = json.loads(data)
        else: 
            self.data = None
        return bool(data)

    
    async def delete(self):
        return bool(await self.redis_client.delete(self.chunk_name))



class Audio(Data):
    def __init__(self, chunk_name: str, redis_client: redis.client.Redis, data: bytes = None):
        super().__init__(chunk_name=chunk_name, key='audio', redis_client=redis_client, data=data)

class Transcript(Data):
    def __init__(self, chunk_name: str, redis_client: redis.client.Redis, data: List = None):
        super().__init__(chunk_name=chunk_name, key='transcription', redis_client=redis_client, data=data)

class Diarisation(Data):
    def __init__(self, chunk_name: str, redis_client: redis.client.Redis, data: List = None):
        super().__init__(chunk_name=chunk_name, key='diarisation', redis_client=redis_client, data=data)

