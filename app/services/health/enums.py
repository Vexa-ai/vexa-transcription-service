"""Enums for health status of dependencies (db, redis, services, etc.)."""
from enum import Enum


class Entry(str, Enum):
    """Dependent components of a service (including the service itself)."""

    SELF = "self"
    REDIS = "redis"

    # External services
    STREAM_QUEUE_SERVICE = "stream_queue_service"
