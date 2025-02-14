"""Base module exceptions."""
from http import HTTPStatus

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from redis.exceptions import (
    DataNotFoundError,
    RedisBaseError,
    RedisConnectionError,
    UserTokenAlreadyExist,
)
from services.utils.exceptions import MeetingIdFormatError


def add_exception_handlers(app: FastAPI) -> None:
    """Adds handlers to the application.

    Args:
        app: FastAPI application.

    Returns:
        None

    """
    # Redis DB module errors
    add_exception_handler(RedisBaseError, internal_server_error_handler)
    add_exception_handler(RedisConnectionError, internal_server_error_handler)
    add_exception_handler(DataNotFoundError, internal_server_error_handler)
    add_exception_handler(UserTokenAlreadyExist, bad_request_error_handler)

    # Custom errors
    add_exception_handler(MeetingIdFormatError, unprocessable_entity_error_handler)


async def unprocessable_entity_error_handler(request: Request, exception: Exception) -> JSONResponse:
    """Handle UNPROCESSABLE_ENTITY error.

    Args:
        request: Request.
        exception: RedisConnectionError.

    Returns:
        JSONResponse with code=422 and error info.

    """
    return JSONResponse({"detail": str(exception)}, status_code=HTTPStatus.UNPROCESSABLE_ENTITY)


async def internal_server_error_handler(request: Request, exception: Exception) -> JSONResponse:
    """Handle INTERNAL_SERVER error.

    Args:
        request: Request.
        exception: RedisConnectionError.

    Returns:
        JSONResponse with code=500 and error info.

    """
    return JSONResponse({"detail": str(exception)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


async def not_found_error_handler(request: Request, exception: Exception) -> JSONResponse:
    """Handle NOT_FOUND error.

    Args:
        request: Request.
        exception: DataNotFoundError.

    Returns:
        JSONResponse with code=404 and error info.

    """
    return JSONResponse({"detail": str(exception)}, status_code=HTTPStatus.NOT_FOUND)


async def bad_request_error_handler(request: Request, exception: Exception) -> JSONResponse:
    """Handle NOT_FOUND error.

    Args:
        request: Request.
        exception: DataNotFoundError.

    Returns:
        JSONResponse with code=404 and error info.

    """
    return JSONResponse({"detail": str(exception)}, status_code=HTTPStatus.BAD_REQUEST)
