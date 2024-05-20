"""Base module exceptions."""
from http import HTTPStatus

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database_redis.exceptions import DataNotFoundError, RedisConnectionError


def add_exception_handlers(app: FastAPI) -> None:
    """Adds handlers to the application.

    Args:
        app: FastAPI application.

    Returns:
        None

    """
    # Redis error handling
    app.add_exception_handler(RedisConnectionError, internal_server_error_handler)
    app.add_exception_handler(DataNotFoundError, not_found_error_handler)


async def internal_server_error_handler(request: Request, exception: RedisConnectionError) -> JSONResponse:
    """Handle INTERNAL_SERVER error.

    Args:
        request: Request.
        exception: RedisConnectionError.

    Returns:
        JSONResponse with code=500 and error info.

    """
    return JSONResponse({"detail": str(exception)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


async def not_found_error_handler(request: Request, exception: DataNotFoundError) -> JSONResponse:
    """Handle NOT_FOUND error.

    Args:
        request: Request.
        exception: DataNotFoundError.

    Returns:
        JSONResponse with code=404 and error info.

    """
    return JSONResponse({"detail": str(exception)}, status_code=HTTPStatus.NOT_FOUND)
