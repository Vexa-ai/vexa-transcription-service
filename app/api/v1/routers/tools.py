from fastapi import APIRouter

from app.api.v1.schemas.tools import DiarizationStart, TranscribingStart
from app.clients.database_redis.connection import get_redis_client
from app.services.audio.redis import Connection, Diarizer, Meeting, Transcriber
from app.settings import settings

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/flush-cache")
async def flush_cache():
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    await client.flushdb()
    return {"message": "cache flushed successfully"}


@router.get("/diarization/queue-size")
async def get_diarization_queue_size():
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    queue_size = await client.scard("diarize:todo")
    return {"amount": queue_size}


@router.post("/diarization/start")
async def start_diarization(diarization_start: DiarizationStart):
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    connection = Connection(client, diarization_start.connection_id, str(diarization_start.user_id))
    await connection.update_timestamps(diarization_start.start_timestamp, diarization_start.end_timestamp)

    meeting = Meeting(client, diarization_start.connection_id)

    await meeting.load_from_redis()
    await meeting.add_connection(connection.id)
    await meeting.set_start_timestamp(diarization_start.start_timestamp)
    meeting.diarizer_last_updated_timestamp = diarization_start.start_timestamp
    meeting.transcriber_last_updated_timestamp = diarization_start.start_timestamp
    diarizer = Diarizer(client)
    await diarizer.add_todo(meeting.meeting_id)
    await meeting.update_diarizer_timestamp(
        diarization_start.start_timestamp,
        diarizer_last_updated_timestamp=diarization_start.diarizer_last_updated_timestamp,
    )
    await meeting.update_redis()


@router.get("/transcribing/queue-size")
async def get_transcribing_queue_size():
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    queue_size = await client.dbsize("transcribe:todo")
    return {"amount": queue_size}


@router.post("/transcribing/start")
async def start_transcribing(transcribing_start: TranscribingStart):
    client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
    connection = Connection(client, transcribing_start.connection_id, str(transcribing_start.user_id))
    await connection.update_timestamps(transcribing_start.start_timestamp, transcribing_start.end_timestamp)

    meeting = Meeting(client, transcribing_start.connection_id)

    await meeting.load_from_redis()
    await meeting.add_connection(connection.id)
    await meeting.set_start_timestamp(transcribing_start.start_timestamp)
    meeting.diarizer_last_updated_timestamp = transcribing_start.start_timestamp
    meeting.transcriber_last_updated_timestamp = transcribing_start.start_timestamp
    transcriber = Transcriber(client)
    await transcriber.add_todo(meeting.meeting_id)
    await meeting.update_transcriber_timestamp(
        transcribing_start.start_timestamp,
        transcriber_last_updated_timestamp=transcribing_start.transcriber_last_updated_timestamp,
    )
    await meeting.update_redis()
