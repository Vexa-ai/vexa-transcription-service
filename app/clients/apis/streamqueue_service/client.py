"""This module contains methods for sending a request to StreamQueue-service."""
import logging
from typing import Any, List

from httpx import (
    ConnectError,
    ConnectTimeout,
    HTTPStatusError,
    ProxyError,
    ReadTimeout,
)

from app.clients.apis.base import BaseAPI
from app.clients.apis.enums import HTTPMethod
from app.clients.apis.streamqueue_service.exceptions import (
    StreamQueueServiceBaseError,
    StreamQueueServiceRequestError,
    StreamQueueServiceTimeoutError,
)
from app.clients.apis.streamqueue_service.schemas import AudioChunkInfo, ExistingConnectionInfo
from app.services.health.schemas import Health
from app.settings import settings

logger = logging.getLogger(__name__)


class StreamQueueServiceAPI(BaseAPI):
    """Class for working with StreamQueue-service by API."""

    def __init__(self):
        pass

    async def get_connections(self) -> List[ExistingConnectionInfo]:
        response_data = await self._process_request(
            method=HTTPMethod.GET,
            url=settings.stream_queue_service_list_connections,
            params={"service_token": settings.stream_queue_service_auth_token},
            headers={"Content-Type": "application/json"},
            timeout=settings.stream_queue_service_request_timeout,
        )
        return [ExistingConnectionInfo(**data) for data in response_data]

    async def fetch_chunks(self, connection_id: str, limit: int) -> List[AudioChunkInfo]:
        response_data = await self._process_request(
            method=HTTPMethod.GET,
            url=f"{settings.stream_queue_service_get_next_chunks}/{connection_id}",
            params={"service_token": settings.stream_queue_service_auth_token, "limit": limit},
            timeout=settings.stream_queue_service_request_timeout,
        )
        if response_data:
            return [AudioChunkInfo(**data) for data in response_data]

        logger.warning("No more chunks available for this connection")
        #     else:
        #         return {"error": "Failed to fetch chunks", "status_code": response.status_code,
        #                 "details": response.text}
        # except httpx.RequestError as e:
        #     return {"error": "An error occurred while requesting chunks", "exception": str(e)}

    async def health(self) -> bool:
        raw_data = await self._process_request(method=HTTPMethod.GET, url=settings.stream_queue_service_health)
        health_info = Health(**raw_data)
        return health_info.is_available

    async def _process_request(self, method: HTTPMethod, url: str, **kwargs) -> Any:
        """Base function to process api requests."""

        try:
            response = await self._send_request(method, url, **kwargs)
            return response

        except HTTPStatusError as ex:
            logger.error(ex)
            raise StreamQueueServiceRequestError(f"[HTTP-{ex.response.status_code}]: {ex}") from ex

        except ConnectTimeout as ex:
            logger.error(ex)
            raise StreamQueueServiceTimeoutError(
                f"{ex} (timeout={settings.stream_queue_service_request_timeout})"
            ) from ex

        except (ConnectError, ConnectTimeout, ProxyError, ReadTimeout) as ex:
            logger.error(ex)
            raise StreamQueueServiceBaseError(ex) from ex
