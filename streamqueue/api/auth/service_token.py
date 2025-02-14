"""Authorization module using string-token (not JWT)."""
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer

from settings import settings


class ServiceTokenAuth(HTTPBearer):
    """Class for service token authentication."""

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> bool:
        """Check if the service token is valid.

        Args:
            request: All meta information about the request.

        Returns:
            True if the service token is valid.

        Raises:
            HTTPException (HTTP-401): Invalid or missing service token.
        """
        header_token = await super().__call__(request)

        if not header_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        token = header_token.credentials

        if token != settings.service_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid service token"
            )

        return True

service_token_auth = ServiceTokenAuth()
