import asyncio
import io
import json
import logging
from datetime import datetime, timezone,timedelta
from uuid import uuid4

import pandas as pd
import torch
from pyannote.audio import Pipeline
from qdrant_client import QdrantClient, models

from app.database_redis import keys
from app.database_redis.connection import get_redis_client
from app.services.audio.audio import AudioSlicer
from app.services.audio.redis import Diarisation, Diarizer, Meeting, best_covering_connection
from app.settings import settings

logger = logging.getLogger(__name__)

# client = QdrantClient("host.docker.internal", timeout=10, port=6333)
client = QdrantClient("qdrant", timeout=10)


def get_stored_knn(emb: list, user_id):
    search_result = client.search(
        collection_name="main",
        query_vector=emb,
        limit=1,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))]
        ),
    )
    if len(search_result) > 0:
        search_result = search_result[0]
        return search_result.payload["speaker_id"], search_result.score
    else:
        return None, None


async def add_new_speaker_emb(emb: list, redis_client, user_id, speaker_id=None):
    logger.info("Adding new speaker...")
    speaker_id = speaker_id if speaker_id else str(uuid4())
    client.upsert(
        collection_name="main",
        wait=True,
        points=[
            models.PointStruct(id=str(uuid4()), vector=emb, payload={"speaker_id": speaker_id, "user_id": user_id})
        ],
    )
    await redis_client.lpush(keys.SPEAKER_EMBEDDINGS, json.dumps((speaker_id, emb.tolist(), user_id)))
    logger.info(f"Added new speaker {speaker_id}")
    return speaker_id


async def process_speaker_emb(emb: list, redis_client, user_id):
    speaker_id, score = get_stored_knn(emb, user_id)
    logger.info(f"score: {score}")

    if speaker_id:
        if score > 0.95:
            pass
        elif score > 0.75:
            await add_new_speaker_emb(emb, redis_client, user_id, speaker_id=speaker_id)
        else:
            speaker_id = await add_new_speaker_emb(emb, redis_client, user_id)
    else:
        speaker_id = await add_new_speaker_emb(emb, redis_client, user_id)

    return str(speaker_id), score


def parse_segment(segment):
    return segment[0].start, segment[0].end, int(segment[-1].split("_")[1])


async def get_next_chunk_start(diarization_result, length, shift):

    if len(diarization_result) > 0:
        last_speech = diarization_result[-1]

        ended_silence = length - last_speech["end"]
        logger.info(ended_silence)
        if ended_silence < 2:
            logger.info("interrupted")
            return last_speech["start"] + shift

        else:
            logger.info("non-interrupted")
            return last_speech["end"] + shift

    else:
        return None


async def process(redis_client, pipeline, max_length=240):
    diarizer = Diarizer(redis_client)
    meeting_id = await diarizer.pop_inprogress()
    print(meeting_id)

    if not meeting_id:
        return

    meeting = Meeting(redis_client, meeting_id)
    await meeting.load_from_redis()
    seek = (meeting.diarizer_seek_timestamp - meeting.start_timestamp).total_seconds()

    current_time = datetime.now(timezone.utc)
    
    connections = await meeting.get_connections()

    connection = best_covering_connection(meeting.diarizer_seek_timestamp, current_time, connections)
    audio_slicer = await AudioSlicer.from_ffmpeg_slice(f"/audio/{connection.id}.webm", seek, max_length)
    slice_duration = audio_slicer.audio.duration_seconds
    audio_data = await audio_slicer.export_data()

    output, embeddings = pipeline(io.BytesIO(audio_data), return_embeddings=True)

    if len(embeddings) == 0:
        logger.info("No embeddings found, skipping...")
        return

    speakers = [await process_speaker_emb(e, redis_client, connection.user_id) for e in embeddings]

    segments = [i for i in output.itertracks(yield_label=True)]
    df = pd.DataFrame([parse_segment(s) for s in segments], columns=["start", "end", "speaker_id"])
    df["speaker"] = df["speaker_id"].replace({i: s[0] for i, s in enumerate(speakers)})
    df["score"] = df["speaker_id"].replace({i: s[1] for i, s in enumerate(speakers)})
    result = df.drop(columns=["speaker_id"]).to_dict("records")

    diarization = Diarisation(meeting_id, redis_client, result)
    await diarization.lpush()

    seek = await get_next_chunk_start(result, slice_duration, seek)
    seek = seek or  seek + slice_duration

    meeting.diarize_seek_timestamp = meeting.start_timestamp+timedelta(seconds=seek)
    await diarizer.remove(meeting.meeting_id)
    await meeting.update_redis()


async def main():
    redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)

    while True:
        await asyncio.sleep(0.1)
        await process(redis_client, pipeline)


if __name__ == "__main__":
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token="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",
    )
    pipeline.to(torch.device("cuda"))
    asyncio.run(main())
