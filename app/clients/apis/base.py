from abc import ABC, abstractmethod
from typing import Any

from httpx import AsyncClient

from app.clients.apis.enums import HTTPMethod


class BaseAPI(ABC):
    """ToDo."""

    @abstractmethod
    async def _process_request(self, **kwargs):
        pass

    @staticmethod
    async def _send_request(method: HTTPMethod, url, **kwargs) -> Any:
        async with AsyncClient() as client:
            response = await client.request(method=method.value, url=url, **kwargs)
            response.raise_for_status()
            return response.json()
