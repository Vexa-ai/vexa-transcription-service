"""Authorization module using string-token (not JWT)."""
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer
from typing import Optional
from app.settings import settings


class ServerToken(HTTPBearer):
    """Class for working with JWT Token.

    Attributes:
        auto_error: automatically raise an error (HTTP-401).

    """

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request, query_token: Optional[str] = None) -> bool:
        """Check the service's ability to access the resource.

        Notes:
            The token can be passed both in the request parameters and in the query parameters.

        Args:
            request: All meta information about the request.
            query_token (optional): Token provided by query parameters.

        Returns:
            True if the service has a valid token value.

        Raises:
            HTTPException (HTTP-401): The service did not provide a token OR the provided token is incorrect.

        """
        if query_token:
            token = query_token

        else:
            header_token = await super().__call__(request)

            if not header_token:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')

            token = header_token.credentials

        if token == settings.service_token:
            return True

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
