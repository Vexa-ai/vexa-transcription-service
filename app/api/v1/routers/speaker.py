from typing import List

from fastapi import APIRouter

from app.api.v1.schemas.speaker import SpeakerEmbeddings
from app.database_redis.connection import get_redis_client
from app.database_redis.dals import SpeakerDAL
from app.settings import settings

router = APIRouter(prefix="/speakers", tags=["speakers"])


# Note: response_model=List[SpeakerEmbeddings] will trigger a validation. This will waste time on the request.
@router.get("/embeddings", responses={200: {"model": List[SpeakerEmbeddings]}})
async def get_embeddings(limit: int = 100) -> List[SpeakerEmbeddings]:
    client = SpeakerDAL(await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password))
    embeddings = await client.get_embeddings(limit)
    return [SpeakerEmbeddings(speaker_id=item[0], user_id=item[2], embedding_data=item[1]) for item in embeddings]
