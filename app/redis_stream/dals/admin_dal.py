"""Module for basic work with Redis admin database (n=1)."""
import logging
from typing import Optional

from redis.dals.base import BaseDAL
from redis.exceptions import UserTokenAlreadyExist
from redis.keys import TOKEN_USER_MAP, USER_ENABLE_STATUS_MAP

logger = logging.getLogger(__name__)


class AdminDAL(BaseDAL):
    """Class for basic work with Redis admin database (n=1)."""

    async def add_token(self, token: str, user_id: str, enable: bool) -> None:
        if await self.get_user_from_token(token) is None:
            await self._redis_client.hset(TOKEN_USER_MAP, token, user_id)
            await self.set_user_enable_status(user_id, enable)

        else:
            raise UserTokenAlreadyExist(f'Token "{token}" already exist')

    async def set_user_enable_status(self, user_id: str, enable_status: bool) -> None:
        await self._redis_client.hset(USER_ENABLE_STATUS_MAP, user_id, str(int(enable_status)))

    async def is_user_enabled(self, user_id: str) -> bool:
        enable_status = await self._redis_client.hget(USER_ENABLE_STATUS_MAP, user_id)
        return bool(int(enable_status)) if enable_status else False

    async def get_user_from_token(self, token: str) -> Optional[str]:
        return await self._redis_client.hget(TOKEN_USER_MAP, token)
