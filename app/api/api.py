"""Contains endpoints for Audio-service."""
from fastapi import APIRouter, Depends

from app.api.service_token import ServiceToken
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.segment import router as segments_router
from app.api.v1.routers.service_tools import router as tools_router
from app.api.v1.routers.speaker import router as embeddings_router

router = APIRouter()

# v1 API endpoints
router.include_router(embeddings_router, prefix="/v1", dependencies=[Depends(ServiceToken())])
router.include_router(health_router, prefix="/v1")
router.include_router(segments_router, prefix="/v1", dependencies=[Depends(ServiceToken())])
router.include_router(tools_router, prefix="/v1", dependencies=[Depends(ServiceToken())])

# you cat place other v1 endpoint or add new v2
