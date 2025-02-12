#!/usr/bin/env python3

import asyncio
import redis.asyncio as redis
import sys
import json
sys.path.append('.')

from app.settings import settings

def format_json(text):
    """Format JSON content if possible."""
    try:
        # Try to parse as JSON
        data = json.loads(text)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except:
        return text

async def inspect_redis():
    """Inspect Redis keys and their contents."""
    # Connect to Redis
    redis_client = redis.from_url(settings.redis_connection)
    
    try:
        # Get all keys
        print("\n=== All Redis Keys ===")
        keys = await redis_client.keys('*')
        for i, key in enumerate(keys, 1):
            key_str = key.decode('utf-8')
            key_type = await redis_client.type(key)
            print(f"\n{i}. Key: {key_str} (Type: {key_type.decode('utf-8')})")
            
            # Get key contents based on type
            if key_type == b'string':
                value = await redis_client.get(key)
                decoded_value = value.decode('utf-8')
                print(f"   Value: {format_json(decoded_value)}")
            
            elif key_type == b'list':
                length = await redis_client.llen(key)
                items = await redis_client.lrange(key, 0, -1)
                print(f"   Length: {length}")
                print("   Items:")
                for item in items[:5]:  # Show first 5 items
                    decoded_item = item.decode('utf-8')
                    print(f"   - {format_json(decoded_item)}")
                if length > 5:
                    print(f"   ... ({length-5} more items)")
            
            elif key_type == b'hash':
                items = await redis_client.hgetall(key)
                print("   Hash contents:")
                for field, value in items.items():
                    field_str = field.decode('utf-8')
                    value_str = value.decode('utf-8')
                    print(f"   {field_str}: {format_json(value_str)}")
            
            elif key_type == b'set':
                members = await redis_client.smembers(key)
                print("   Set members:")
                for member in members:
                    decoded_member = member.decode('utf-8')
                    print(f"   - {format_json(decoded_member)}")
            
            elif key_type == b'zset':
                items = await redis_client.zrange(key, 0, -1, withscores=True)
                print("   Sorted set items:")
                for member, score in items:
                    decoded_member = member.decode('utf-8')
                    print(f"   - {format_json(decoded_member)} (score: {score})")
                    
    finally:
        await redis_client.aclose()  # Using aclose() instead of deprecated close()

if __name__ == "__main__":
    asyncio.run(inspect_redis()) 