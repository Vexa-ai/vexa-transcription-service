"""Module containing methods that are launched when the application starts/stops."""
import asyncio
import logging

from fastapi import FastAPI

from app.settings import settings
from audio.app.tasks.parse_stream import ProcessConnectionTask

logger = logging.getLogger(__name__)


def add_event_handlers(app: FastAPI) -> None:
    app.add_event_handler("startup", check_and_process_connections)


async def check_and_process_connections():
    logger.info(settings.check_and_process_connections_interval_sec)
    if settings.check_and_process_connections_interval_sec:
        service = ProcessConnectionTask(
            interval=settings.check_and_process_connections_interval_sec,
            delay=0,
            loop=asyncio.get_running_loop(),
        )
        await service.start()

    else:
        logger.warning("Connection processing disabled")
