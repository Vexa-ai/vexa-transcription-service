"""Redis Reporting Utility.

This script generates a comprehensive report of all data stored in Redis,
including connections, meetings, transcriptions, and queue states.
"""
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from redis.asyncio.client import Redis
from redis.exceptions import ResponseError

from app.redis_transcribe.connection import get_redis_client
from app.redis_transcribe.keys import (
    CONNECTION,
    MEETING,
    SEGMENTS_TRANSCRIBE,
    AUDIO_2_TRANSCRIBE_QUEUE,
    TRANSCRIBE_READY,
    START_TIMESTAMP,
    END_TIMESTAMP,
    TRANSCRIBE_SEEK_TIMESTAMP,
    TRANSCRIBER_LAST_UPDATED_TIMESTAMP,
)

class RedisReporter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        
    async def get_all_keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching the pattern."""
        return await self.redis.keys(pattern)
    
    async def get_key_type(self, key: str) -> str:
        """Get the type of a Redis key."""
        return await self.redis.type(key)
    
    async def get_key_value(self, key: str) -> Dict[str, Any]:
        """Get the value and type information for a key."""
        try:
            key_type = await self.get_key_type(key)
            
            if key_type == "string":
                value = await self.redis.get(key)
            elif key_type == "hash":
                value = await self.redis.hgetall(key)
            elif key_type == "list":
                value = await self.redis.lrange(key, 0, -1)
            elif key_type == "set":
                value = list(await self.redis.smembers(key))
            elif key_type == "zset":
                value = await self.redis.zrange(key, 0, -1, withscores=True)
            else:
                value = None
                
            return {
                "type": key_type,
                "value": value
            }
        except ResponseError as e:
            return {
                "type": "error",
                "value": str(e)
            }
        except Exception as e:
            return {
                "type": "error",
                "value": f"Unexpected error: {str(e)}"
            }

    async def get_connections_report(self) -> Dict[str, Any]:
        """Get report on all connections."""
        connections = {}
        pattern = f"{CONNECTION}:*"
        keys = await self.get_all_keys(pattern)
        
        for key in keys:
            connections[key] = await self.get_key_value(key)
        
        return connections

    async def get_meetings_report(self) -> Dict[str, Any]:
        """Get report on all meetings."""
        meetings = {}
        pattern = f"{MEETING}:*"
        keys = await self.get_all_keys(pattern)
        
        for key in keys:
            meetings[key] = await self.get_key_value(key)
        
        return meetings

    async def get_transcriptions_report(self) -> Dict[str, Any]:
        """Get report on all transcriptions."""
        transcriptions = {}
        pattern = f"{SEGMENTS_TRANSCRIBE}:*"
        keys = await self.get_all_keys(pattern)
        
        for key in keys:
            transcriptions[key] = await self.get_key_value(key)
        
        return transcriptions

    async def get_queues_report(self) -> Dict[str, Any]:
        """Get report on transcription queues."""
        return {
            "audio_to_transcribe": await self.get_key_value(AUDIO_2_TRANSCRIBE_QUEUE),
            "transcribe_ready": await self.get_key_value(TRANSCRIBE_READY)
        }

    async def generate_full_report(self) -> Dict[str, Any]:
        """Generate a comprehensive report of all Redis data."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "connections": await self.get_connections_report(),
            "meetings": await self.get_meetings_report(),
            "transcriptions": await self.get_transcriptions_report(),
            "queues": await self.get_queues_report(),
        }
        return report

async def main():
    """Main function to generate and display the Redis report."""
    # Replace these with your Redis connection details
    redis_client = await get_redis_client(
        host="localhost",  # Replace with your Redis host
        port=6379,        # Replace with your Redis port
        password=None,    # Replace with your Redis password if any
        db=0             # Replace with your Redis DB number
    )
    
    try:
        reporter = RedisReporter(redis_client)
        report = await reporter.generate_full_report()
        
        # Print the report in a formatted way
        print("\n=== Redis Database Report ===")
        print(f"Generated at: {report['timestamp']}\n")
        
        print("=== Connections ===")
        print(json.dumps(report['connections'], indent=2))
        
        print("\n=== Meetings ===")
        print(json.dumps(report['meetings'], indent=2))
        
        print("\n=== Transcriptions ===")
        print(json.dumps(report['transcriptions'], indent=2))
        
        print("\n=== Queues ===")
        print(json.dumps(report['queues'], indent=2))
        
    finally:
        await redis_client.close()

if __name__ == "__main__":
    asyncio.run(main()) 