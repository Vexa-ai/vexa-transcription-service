from typing import List

from fastapi import APIRouter

from app.api.v1.schemas.segment import Segment
from app.database_redis.connection import get_redis_client
from app.database_redis.dals import SegmentDAL
from app.settings import settings

router = APIRouter(prefix="/segments", tags=["segments"])


# Note: response_model=List[Segment] will trigger a validation. This will waste time on the request.
@router.get("/all", responses={200: {"model": List[Segment]}})
async def get_all_segments() -> List[Segment]:
    client = SegmentDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    all_segments_data = await client.get_all_segments()
    return [Segment(meeting_id=meeting_id, data=data) for meeting_id, data in all_segments_data.items()]


@router.get("/transcribe")
async def get_transcribe_segments(limit: int = 100):
    """Fetches the next set of chunks from the specified connection queue.
    The number of chunks retrieved can be specified by the num_chunks parameter.
    """
    client = SegmentDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    segments = await client.get_diarize_segments(limit)
    return {"chunks": segments}


@router.get("/diarize")
async def get_diarize_segments(limit: int = 100):
    """Fetches the next set of chunks from the specified connection queue.
    The number of chunks retrieved can be specified by the num_chunks parameter.
    """
    client = SegmentDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    segments = await client.get_transcribe_segments(limit)
    return {"chunks": segments}
