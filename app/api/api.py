"""Contains endpoints for engine service."""
from fastapi import APIRouter

from app.api.v1.routers.embeddings import router as embeddings_router
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.segments import router as segments_router
from app.api.v1.routers.tools import router as tools_router

router = APIRouter()

# v1 API endpoints
router.include_router(embeddings_router, prefix="/v1")
router.include_router(health_router, prefix="/v1")
router.include_router(segments_router, prefix="/v1")
router.include_router(tools_router, prefix="/v1")

# you cat place other v1 endpoint or add new v2
