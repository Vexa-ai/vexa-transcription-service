from typing import List

from fastapi import APIRouter

from app.api.v1.schemas.segment import Segment
from app.clients.database_redis.connection import get_redis_client
from app.clients.database_redis.dals import SegmentDAL
from app.settings import settings

router = APIRouter(prefix="/segments", tags=["segments"])


# Note: response_model=List[Segment] will trigger a validation. This will waste time on the request.
@router.get("/transcriber", responses={200: {"model": List[Segment]}})
async def get_transcribe_segments(limit: int = 100) -> List[Segment]:
    """Fetches the next set of chunks from the specified connection queue.
    The number of chunks retrieved can be specified by the num_chunks parameter.
    """
    client = SegmentDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    segments_data = await client.get_transcribe_segments(limit)
    return [Segment(meeting_id=meeting_id, data=data) for meeting_id, data in segments_data.items()]


@router.get("/diarizer", responses={200: {"model": List[Segment]}})
async def get_diarize_segments(limit: int = 100) -> List[Segment]:
    """Fetches the next set of chunks from the specified connection queue.
    The number of chunks retrieved can be specified by the num_chunks parameter.
    """
    client = SegmentDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    segments_data = await client.get_diarize_segments(limit)
    return [Segment(meeting_id=meeting_id, data=data) for meeting_id, data in segments_data.items()]
