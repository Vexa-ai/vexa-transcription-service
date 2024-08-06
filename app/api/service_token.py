"""Authorization module using string-token (not JWT)."""
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer

from app.settings import settings


class ServiceToken(HTTPBearer):
    """Class for working with service's token.

    Attributes:
        auto_error: automatically raise an error (HTTP-401).

    """

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request, service_token: Optional[str] = None) -> bool:
        """Check the service's ability to access the resource.

        Notes:
            The token can be passed both in the request parameters and in the query parameters.

        Args:
            request: All meta information about the request.
            service_token (optional): Token provided by query parameters.

        Returns:
            True if the service has a valid token value.

        Raises:
            HTTPException (HTTP-401): The service did not provide a token OR the provided token is incorrect.

        """
        if service_token is None:
            header_token = await super().__call__(request)

            if not header_token:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

            service_token = header_token.credentials

        if service_token == settings.service_token:
            return True

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
