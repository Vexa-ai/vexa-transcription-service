"""Endpoints for health check."""
from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from app.services.health import health
from app.services.health.schemas import Health, HealthCommon

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
async def get_health() -> Health:
    """Get a positive health status.

    Returns:\n
        200 OK:
            {
                "is_available": true
            }

        404 Not Found:
            {
                "detail": "Not Found"
            }

    """
    return Health(is_available=True)


@router.get("/hc", response_model=HealthCommon)
async def health_check() -> JSONResponse:
    """Get the health status of the current service and dependencies (db, redis, etc.).

    Returns:\n
        503 SERVICE_UNAVAILABLE:
            {
              "is_available": false,
              "entries": {
                "self": {
                  "is_available": true
                },
                "redis": {
                  "is_available": false
                },
                "stream_queue_service": {
                  "is_available": true
                }
              }
            }
        200 OK:
            {
              "is_available": true,
              "entries": {
                "self": {
                  "is_available": true
                },
                "redis": {
                  "is_available": true
                },
                "stream_queue_service": {
                  "is_available": true
                }
              }
            }

        404 Not Found:
            {
                "detail": "Not Found"
            }

    """
    health_check_result = await health.health_check()
    status_code = HTTP_200_OK if health_check_result.is_available else HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=jsonable_encoder(health_check_result))
