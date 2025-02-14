"""Contains endpoints for StreamingQueue-service."""
from fastapi import APIRouter, Depends

from api.auth.service_token import ServiceTokenAuth
from api.auth.user_token import UserTokenAuth
from api.routers.extension import router as extension_router
from api.routers.tools import router as tools_router
from api.routers.user import router as user_router

router = APIRouter()

# v1 API endpoints
V1 = "/v1"

router.include_router(extension_router, prefix=V1, dependencies=[Depends(UserTokenAuth())])
router.include_router(user_router, prefix=V1, dependencies=[Depends(ServiceTokenAuth())])
router.include_router(tools_router, prefix=V1, dependencies=[Depends(ServiceTokenAuth())])

# you cat place other v1 endpoint or add new v2
