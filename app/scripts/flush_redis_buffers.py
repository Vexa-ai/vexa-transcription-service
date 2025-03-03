#!/usr/bin/env python
"""Utility script to flush Redis audio buffers to disk.

This script can be used to:
1. List all audio buffers currently in Redis
2. Flush specific audio buffers to disk
3. Flush all audio buffers to disk

Usage:
    python flush_redis_buffers.py list
    python flush_redis_buffers.py flush <connection_id>
    python flush_redis_buffers.py flush-all
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from app.redis_transcribe.connection import get_redis_client
from app.settings import settings
from shared_lib.redis.keys import AUDIO_BUFFER

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def list_buffers(redis_client):
    """List all audio buffers in Redis."""
    pattern = f"{AUDIO_BUFFER}:*"
    buffers = []
    
    async for key in redis_client.scan_iter(match=pattern):
        connection_id = key.split(':')[1]
        size = await redis_client.strlen(key)
        ttl = await redis_client.ttl(key)
        
        buffers.append({
            'connection_id': connection_id,
            'size': size,
            'ttl': ttl  # Time to live in seconds
        })
        
    return buffers

async def flush_buffer(redis_client, connection_id, output_dir="/data/audio"):
    """Flush a specific audio buffer to disk."""
    redis_key = f"{AUDIO_BUFFER}:{connection_id}"
    hex_encoded_data = await redis_client.get(redis_key)
    
    if not hex_encoded_data:
        logger.error(f"No audio buffer found for connection {connection_id}")
        return False
    
    try:
        # Convert hex encoded string back to binary data
        data = bytes.fromhex(hex_encoded_data)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Write to disk
        file_path = os.path.join(output_dir, f"{connection_id}.webm")
        with open(file_path, "wb") as f:
            f.write(data)
            
        logger.info(f"Flushed buffer for connection {connection_id} to {file_path} ({len(data)} bytes)")
        return True
    
    except ValueError as e:
        logger.error(f"Failed to decode hex data from Redis for connection {connection_id}: {e}")
        return False

async def flush_all_buffers(redis_client, output_dir="/data/audio"):
    """Flush all audio buffers to disk."""
    buffers = await list_buffers(redis_client)
    
    if not buffers:
        logger.info("No audio buffers found in Redis")
        return 0
    
    success_count = 0
    for buffer in buffers:
        connection_id = buffer['connection_id']
        if await flush_buffer(redis_client, connection_id, output_dir):
            success_count += 1
    
    logger.info(f"Flushed {success_count}/{len(buffers)} audio buffers to disk")
    return success_count

async def main(command, *args):
    """Main entry point."""
    # Initialize Redis client
    redis_client = await get_redis_client(
        settings.redis_host, 
        settings.redis_port,
        settings.redis_password
    )
    
    if command == 'list':
        buffers = await list_buffers(redis_client)
        if not buffers:
            print("No audio buffers found in Redis")
        else:
            print(f"Found {len(buffers)} audio buffers in Redis:")
            for buffer in buffers:
                print(f"  Connection: {buffer['connection_id']}, Size: {buffer['size']} bytes, TTL: {buffer['ttl']} seconds")
    
    elif command == 'flush':
        if not args:
            print("Error: Missing connection ID. Usage: python flush_redis_buffers.py flush <connection_id>")
            return 1
        
        connection_id = args[0]
        output_dir = args[1] if len(args) > 1 else "/data/audio"
        
        if await flush_buffer(redis_client, connection_id, output_dir):
            print(f"Successfully flushed buffer for connection {connection_id}")
        else:
            print(f"Failed to flush buffer for connection {connection_id}")
            return 1
    
    elif command == 'flush-all':
        output_dir = args[0] if args else "/data/audio"
        count = await flush_all_buffers(redis_client, output_dir)
        print(f"Flushed {count} audio buffers to disk")
    
    else:
        print("Unknown command. Usage:")
        print("  python flush_redis_buffers.py list")
        print("  python flush_redis_buffers.py flush <connection_id> [output_dir]")
        print("  python flush_redis_buffers.py flush-all [output_dir]")
        return 1
    
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Missing command. Usage:")
        print("  python flush_redis_buffers.py list")
        print("  python flush_redis_buffers.py flush <connection_id> [output_dir]")
        print("  python flush_redis_buffers.py flush-all [output_dir]")
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    exit_code = asyncio.run(main(command, *args))
    sys.exit(exit_code) 