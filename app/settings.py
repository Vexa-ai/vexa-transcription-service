"""Processing of settings coming from environment variables."""

import os
from pathlib import Path
from typing import Optional, Set
import logging.config
import sys

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Get values from environment variables with defaults
    redis_host: str = os.getenv('REDIS_HOST')
    redis_port: int = int(os.getenv('REDIS_PORT'))
    redis_password: str | None = os.getenv('REDIS_PASSWORD')
    audio_chunk_duration_sec: int = int(os.getenv('AUDIO_CHUNK_DURATION_SEC'))
    segment_size_sec: int = int(os.getenv('SEGMENT_SIZE_SEC'))
    processing_threads: int = int(os.getenv('PROCESSING_THREADS'))
    check_and_process_connections_interval_sec: int = int(os.getenv('CHECK_AND_PROCESS_CONNECTIONS_INTERVAL_SEC'))
    speaker_delay_sec: int = int(os.getenv('SPEAKER_DELAY_SEC'))
    whisper_service_url: str = os.getenv('WHISPER_SERVICE_URL')
    whisper_api_token: str = os.getenv('WHISPER_API_TOKEN')
    redis_password: str | None = os.getenv('REDIS_PASSWORD')
    transcriber_step_sec: int = int(os.getenv('TRANSCRIBER_STEP_SEC', '1'))
    max_audio_length_sec: int = int(os.getenv('MAX_AUDIO_LENGTH_SEC', '5'))
    
    speaker_delay_sec: int = 1


    model_config = {
        "env_nested_delimiter": "__",
        "case_sensitive": False  # This will make it case-insensitive
    }

    @property
    def redis_connection(self) -> str:
        """str: String to connect to Redis database."""
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"


# # Configure logging
# try:
#     logging.config.fileConfig(fname=PROJECT_ROOT / "logger.conf", disable_existing_loggers=False)
# except Exception as e:
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#     )
#     # Remove or comment out the warning log
#     # logger.warning("Could not load logger.conf: %s", str(e))

# Initialize settings
settings = Settings()
