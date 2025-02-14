from typing import List

from fastapi import APIRouter

from api.schemas import UserResponse, UserSetEnableStatus, UserTokenCreate
from redis_db.shared_lib..connection import get_redis_client
from redis_db.shared_lib..dals.admin_dal import AdminDAL
from settings import settings

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/add-token")
async def add_user_token(user_token: UserTokenCreate) -> UserResponse:
    admin_dal = AdminDAL(
        await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password, db=1)
    )
    await admin_dal.add_token(user_token.token, user_token.user_id, user_token.enable_status)
    return UserResponse(user_id=user_token.user_id, enabled=user_token.enable_status)


@router.post("/set-status")
async def set_users_status(user_statues: List[UserSetEnableStatus]) -> List[UserResponse]:
    admin_dal = AdminDAL(
        await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password, db=1)
    )
    response = []

    for user_status in user_statues:
        await admin_dal.set_user_enable_status(user_status.user_id, user_status.enable_status)
        response.append(UserResponse(user_id=user_status.user_id, enabled=user_status.enable_status))

    return response
