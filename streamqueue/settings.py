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
    api_port: int = int(os.getenv('TRANSCRIPTION_SERVICE_API_PORT'))
    audio_chunk_duration_sec: int = int(os.getenv('AUDIO_CHUNK_DURATION_SEC'))

    service_token: str = os.getenv('TRANSCRIPTION_SERVICE_API_TOKEN')
    
    speaker_delay_sec: int = 1


    model_config = {
        "env_nested_delimiter": "__",
        "case_sensitive": False  # This will make it case-insensitive
    }

    @property
    def redis_connection(self) -> str:
        """str: String to connect to Redis database."""
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"


# Configure project root path and add to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

# Configure logging
logging.config.fileConfig(fname=PROJECT_ROOT / "logger.conf", disable_existing_loggers=False)

# Initialize settings
settings = Settings()
