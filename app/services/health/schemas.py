"""Validators for health status of services.

Classes are developed in accordance with the current KSUP `.net` services of KSUP: ADOC and ProjectService.
"""
from typing import Dict

from pydantic import BaseModel

from app.services.health.enums import Entry


class Health(BaseModel):
    """Service health info."""

    is_available: bool


class HealthCommon(BaseModel):
    """Service health info with dependencies (db etc.) used in `hc` endpoint."""

    is_available: bool  # total status
    entries: Dict[Entry, Health]
