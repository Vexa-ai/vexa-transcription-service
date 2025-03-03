"""Test script for Redis-based audio processing."""
import asyncio
import logging
import os
import io
import tempfile
from uuid import uuid4

from app.redis_transcribe.connection import get_redis_client
from app.settings import settings
from app.services.audio.processor import Processor
from app.services.audio.audio import AudioSlicer
from shared_lib.redis.dals.audio_chunk_dal import AudioChunkDAL
from shared_lib.redis.models import AudioChunkModel
from shared_lib.redis.keys import AUDIO_BUFFER
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def upload_test_audio(audio_chunk_dal, connection_id, user_id, meeting_id=None):
    """Upload test audio chunks to Redis."""
    # Simulate audio chunks (using small chunks for testing)
    chunks = [
        b'\x00\x01\x02\x03\x04\x05',
        b'\x06\x07\x08\x09\x0A\x0B',
        b'\x0C\x0D\x0E\x0F\x10\x11'
    ]
    
    server_timestamp = datetime.now(timezone.utc)
    user_timestamp = server_timestamp
    
    for i, chunk in enumerate(chunks):
        chunk_hex = chunk.hex()
        
        # Create a chunk model
        chunk_obj = AudioChunkModel(
            chunk=chunk_hex,
            user_timestamp=user_timestamp.isoformat(),
            server_timestamp=server_timestamp.isoformat(),
            meeting_id=meeting_id or connection_id,
            user_id=user_id,
            audio_chunk_duration_sec=0.5,  # 0.5 seconds per chunk
            audio_chunk_number=i
        )
        
        # Add to Redis
        await audio_chunk_dal.add_chunk(connection_id, chunk_obj.model_dump())
        
        # Increment timestamps
        user_timestamp = user_timestamp.replace(microsecond=user_timestamp.microsecond + 500000)
        server_timestamp = server_timestamp.replace(microsecond=server_timestamp.microsecond + 500000)
    
    return len(chunks)

async def test_redis_audio_processing():
    """Test Redis-based audio processing."""
    logger.info("Starting Redis audio processing test")
    
    # Initialize Redis client
    redis_client = await get_redis_client(
        settings.redis_host, 
        settings.redis_port,
        settings.redis_password
    )
    
    # Create processor and audio chunk DAL
    processor = Processor()
    await processor.setup()
    audio_chunk_dal = AudioChunkDAL(redis_client)
    
    # Generate unique IDs for testing
    connection_id = f"test-conn-{uuid4()}"
    user_id = uuid4()
    meeting_id = f"test-meeting-{uuid4()}"
    
    # Upload test audio
    chunk_count = await upload_test_audio(
        audio_chunk_dal, 
        connection_id, 
        user_id, 
        meeting_id
    )
    logger.info(f"Uploaded {chunk_count} test audio chunks for connection {connection_id}")
    
    # Process connection
    result = await processor.writestream2file(connection_id)
    logger.info(f"Processed connection {connection_id}, result: {result}")
    
    # Verify data in Redis
    redis_key = f"{AUDIO_BUFFER}:{connection_id}"
    hex_encoded_buffer = await redis_client.get(redis_key)
    
    if hex_encoded_buffer:
        try:
            # Convert hex encoded string back to binary data
            buffer_data = bytes.fromhex(hex_encoded_buffer)
            logger.info(f"Found audio buffer in Redis ({len(buffer_data)} bytes)")
            
            # Test AudioSlicer from Redis
            audio_slicer = await AudioSlicer.from_redis_slice(
                redis_client,
                connection_id,
                0.0,  # Start at beginning
                5.0    # 5 seconds duration
            )
            
            # Export and validate
            audio_data = await audio_slicer.export_data()
            logger.info(f"Exported {len(audio_data)} bytes of audio data from slicer")
            assert len(audio_data) > 0, "Expected non-empty audio data from slicer"
        except ValueError as e:
            logger.error(f"Failed to decode hex data from Redis: {e}")
            assert False, f"Failed to decode hex data from Redis: {e}"
    else:
        logger.error(f"No audio buffer found in Redis for {connection_id}")
    
    # Clean up test data
    await redis_client.delete(redis_key)
    logger.info("Test complete")

if __name__ == "__main__":
    asyncio.run(test_redis_audio_processing()) 