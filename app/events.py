"""Module containing methods that are launched when the application starts/stops."""
import asyncio

from fastapi import FastAPI

from app.settings import settings
from app.utils.periodic_services.process_connections import ProcessConnectionService


def add_event_handlers(app: FastAPI) -> None:
    app.add_event_handler("startup", check_and_process_connections)


async def check_and_process_connections():
    if settings.check_and_process_connections_interval_sec:
        service = ProcessConnectionService(
            interval=settings.check_and_process_connections_interval_sec,
            delay=0,
            loop=asyncio.get_running_loop(),
        )
        await service.start()
