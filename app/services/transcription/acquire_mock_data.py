"""Module for storing and loading mock transcription and speaker data."""
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import asyncio
from datetime import datetime
import aiohttp
import logging
from app.redis_transcribe.connection import get_redis_client
from app.settings import settings
from app.services.transcription.processor import Processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def prepare_mock_data(transcription_segments: List[Any], speaker_data: List[str]) -> Dict:
    """Prepare mock data from real data for storage
    
    Args:
        transcription_segments: Raw transcription segments from Whisper
        speaker_data: Raw speaker data from Redis (list of JSON strings)
        
    Returns:
        Dictionary containing both datasets ready for JSON storage
    """
    logger.info(f"Preparing mock data with {len(transcription_segments)} segments and {len(speaker_data)} speaker entries")
    return {
        "transcription_segments": transcription_segments,
        "speaker_data": speaker_data
    }

def save_mock_data(data: Dict, file_path: str = "mock_data.json") -> None:
    """Save mock data to JSON file.
    
    Args:
        data: Dictionary containing transcription_segments and speaker_data
        file_path: Path to save the JSON file
    """
    logger.info(f"Saving mock data to {file_path}")
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Mock data saved successfully to {file_path}")

def load_mock_data(file_path: str = "mock_data.json") -> Dict:
    """Load mock data from JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary containing transcription_segments and speaker_data
    """
    logger.info(f"Loading mock data from {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    logger.info(f"Loaded mock data with {len(data['transcription_segments'])} segments and {len(data['speaker_data'])} speaker entries")
    return data

async def acquire_and_save_mock_data(processor, redis_client, output_file: str = "mock_data.json") -> None:
    """Acquire real data and save as mock data
    
    Args:
        processor: Processor instance
        redis_client: Redis client instance
        output_file: Path to save the mock data
    """
    logger.info("Starting data acquisition")
    
    # Get transcription data
    logger.info("Reading audio data from processor")
    ok = await processor.read(max_length=240)
    if not ok:
        logger.error("Failed to read audio data")
        raise Exception("Failed to read audio data")
    
    logger.info("Sending request to Whisper service")
    headers = {"Authorization": f"Bearer {processor.whisper_api_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            processor.whisper_service_url, 
            data=processor.audio_data, 
            headers=headers
        ) as response:
            if response.status != 200:
                logger.error(f"Transcription failed with status {response.status}")
                raise Exception(f"Transcription failed with status {response.status}")
            logger.info("Received response from Whisper service")
            result = await response.json()
    
    transcription_data = result['segments']
    logger.info(f"Got {len(transcription_data)} transcription segments")
    
    # Get speaker data
    logger.info("Fetching speaker data from Redis")
    speaker_data = await redis_client.lrange("speaker_data", start=0, end=-1)
    logger.info(f"Got {len(speaker_data)} speaker data entries")
    
    # Prepare and save mock data
    mock_data = prepare_mock_data(transcription_data, speaker_data)
    save_mock_data(mock_data, output_file)
    
    return mock_data

# Example usage in notebook:
"""
from app.services.transcription.acquire_mock_data import acquire_and_save_mock_data

# Setup (as in your notebook)
redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
processor = Processor(redis_client)
processor.whisper_service_url = 'http://host.docker.internal:8033'

# Acquire and save mock data
mock_data = await acquire_and_save_mock_data(processor, redis_client)
"""

# Save mock data if this file is run directly
if __name__ == "__main__":
    async def main():
        logger.info("Starting mock data acquisition script")
        
        # Setup
        logger.info("Setting up Redis client and processor")
        redis_client = await get_redis_client(
            settings.redis_host, 
            settings.redis_port,
            settings.redis_password
        )
        logger.info("Redis client initialized")
        
        processor = Processor(redis_client)
        processor.whisper_service_url = 'http://host.docker.internal:8033'
        logger.info(f"Processor initialized with Whisper URL: {processor.whisper_service_url}")
        
        try:
            # Acquire and save mock data
            logger.info("Starting mock data acquisition")
            mock_data = await acquire_and_save_mock_data(processor, redis_client)
            logger.info("Mock data acquisition completed successfully")
            print(f"Mock data saved successfully!")
            print(f"Transcription segments: {len(mock_data['transcription_segments'])}")
            print(f"Speaker data entries: {len(mock_data['speaker_data'])}")
        except Exception as e:
            logger.error(f"Error acquiring mock data: {e}", exc_info=True)
            print(f"Error acquiring mock data: {e}")
        finally:
            logger.info("Closing Redis client")
            await redis_client.close()
            logger.info("Redis client closed")

    # Run the async main function
    logger.info("Starting main execution")
    asyncio.run(main())
    logger.info("Script completed") 