"""Processing of settings coming from environment variables."""
import logging.config
from pathlib import Path
from typing import Optional

from pydantic import AnyUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Class for app settings (from envs)."""

    service_version: str = "0.1.0"
    service_name: str = "Audio API"
    service_api_host: str = "0.0.0.0"
    service_api_port: int = 8000
    service_token: str = "service_token"

   # check_and_process_connections_interval_sec: Optional[float] = None  #TODO this commented out causion problem


#changed to str
    stream_queue_service_list_connections: str 
    stream_queue_service_flush_cache: str
    stream_queue_service_get_next_chunks: str
    stream_queue_service_health: str
    stream_queue_service_health_check: str
    stream_queue_service_request_timeout: int = 120
    stream_queue_service_auth_token: str

    redis_host: str
    redis_port: int
    redis_password: Optional[str] = None

    class Config:
        # filename that contains environment variables
        env_file = Path(__file__).absolute().parent.parent / ".env"
        extra = "allow"


logging.config.fileConfig(fname=Path(__file__).parent / "logger.conf", disable_existing_loggers=False)
settings = Settings()
