"""Endpoints used by Chrome extension """
from datetime import datetime
from typing import Optional
import logging

from dateutil import parser
from dateutil.tz import UTC
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_201_CREATED

from api.schemas import TokenValidationResult
from api.schemas.extension import SourceType
from shared_lib.redis.connection import get_redis_client
from services.extension_processor import ExtensionProcessor
from streamqueue.settings import settings

logger = logging.getLogger("app")
router = APIRouter(prefix="/extension", tags=["extension"])


@router.get("/check-token")
async def check_token(request: Request) -> TokenValidationResult:
    user_id = request.state.user_id
    logger.info(f"Token check for user {user_id}")
    return TokenValidationResult(is_valid=bool(user_id))


@router.put("/audio")
async def audio_endpoint(
    request: Request,
    i: int,
    connection_id: str,
    source: SourceType = SourceType.GOOGLE_MEET,  # ToDo: will be used later
    meeting_id: Optional[str] = None,
    ts: Optional[int] = None,  # user's timestamp
) -> JSONResponse:
    # For chunk, and connection_start
    server_datetime: datetime = parser.parse(datetime.utcnow().isoformat()).astimezone(UTC)
    user_id = request.state.user_id
    data = await request.body()

    logger.info(f"Received audio chunk {i} for meeting {meeting_id} from user {user_id}")
    logger.debug(f"Audio details: connection_id={connection_id}, timestamp={ts}, size={len(data)}")

    try:
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        extension_process = ExtensionProcessor(redis_client)
        await extension_process.process_audio(
            user_id=user_id,
            connection_id=connection_id,
            meeting_id=meeting_id,
            audio_chunk_number=i,
            chunk=data.hex(),
            server_datetime=server_datetime,
            user_timestamp=ts,
        )
        logger.info(f"Successfully processed audio chunk {i} for meeting {meeting_id}")
        return JSONResponse(status_code=HTTP_200_OK, content={"message": "Chunk received", "connection_id": connection_id})
    except Exception as e:
        logger.error(f"Error processing audio chunk {i}: {str(e)}", exc_info=True)
        raise


@router.put("/speakers")
async def speakers_speech(
    request: Request,
    connection_id: str,
    meeting_id: Optional[str] = None,
    ts: Optional[int] = None,  # user's timestamp
) -> JSONResponse:
    server_datetime: datetime = parser.parse(datetime.utcnow().isoformat()).astimezone(UTC)
    user_id = request.state.user_id
    
    try:
        data = await request.json()
        logger.info(f"Received speakers data for meeting {meeting_id} from user {user_id}")
        logger.info(f"Raw speakers data: {data}")
        logger.info(f"Data type: {type(data)}")
        if isinstance(data, list) and len(data) > 0:
            logger.info(f"First item type: {type(data[0])}")
            logger.info(f"First item: {data[0]}")
        
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        extension_process = ExtensionProcessor(redis_client)
        await extension_process.process_speakers_speech(
            user_id=user_id,
            connection_id=connection_id,
            meeting_id=meeting_id,
            speakers_data=data,  # Example: [["s1", "1001111111"], ["s2", "1011110100"], ...]
            server_datetime=server_datetime,
            user_timestamp=ts,
        )
        logger.info(f"Successfully processed speakers data for meeting {meeting_id}")
        return JSONResponse(status_code=HTTP_201_CREATED, content={"message": "Speaker created"})
    except Exception as e:
        logger.error(f"Error processing speakers data: {str(e)}", exc_info=True)
        logger.error(f"Full request data: {await request.body()}")
        raise
