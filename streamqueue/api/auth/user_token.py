"""Authorization module using string-token (not JWT)."""
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer

from redis_db.shared_lib..connection import get_redis_client
from redis_db.shared_lib..dals.admin_dal import AdminDAL
from settings import settings


class UserTokenAuth(HTTPBearer):
    """Class for working with user's token.

    Attributes:
        auto_error: automatically raise an error (HTTP-401).

    """

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request, token: Optional[str] = None) -> bool:
        """Check the service's ability to access the resource.

        Notes:
            The token can be passed both in the request parameters and in the query parameters.

        Args:
            request: All meta information about the request.
            token (optional): Token provided by query parameters.

        Returns:
            True if the service has a valid token value.

        Raises:
            HTTPException (HTTP-401): The service did not provide a token OR the provided token is incorrect.

        """
        if token is None:
            header_token = await super().__call__(request)

            if not header_token:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

            token = header_token.credentials

        admin_dal = AdminDAL(
            await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password, db=1)
        )
        user_id = await admin_dal.get_user_from_token(token)

        if user_id:
            is_user_enabled = await admin_dal.is_user_enabled(user_id)

            if is_user_enabled:
                request.state.user_id = user_id
                return True

            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbitten")

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
