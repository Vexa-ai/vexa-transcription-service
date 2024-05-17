import asyncio
import io
import json
import logging
from uuid import uuid4

import pandas as pd
import torch
from pyannote.audio import Pipeline
from qdrant_client import QdrantClient, models

from app.database_redis import keys
from app.database_redis.connection import get_redis_client
from app.services.audio.redis import Audio, Diarisation
from app.settings import settings

logger = logging.getLogger(__name__)

# client = QdrantClient("host.docker.internal", timeout=10, port=6333)
client = QdrantClient("qdrant", timeout=10)


async def __get_next_chunk_start(diarization_result, length, shift):

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
    
    

def get_stored_knn(emb: list, client_id):
    search_result = client.search(
        collection_name="main",
        query_vector=emb,
        limit=1,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="client_id", match=models.MatchValue(value=client_id))]
        ),
    )
    if len(search_result) > 0:
        search_result = search_result[0]
        return search_result.payload["speaker_id"], search_result.score
    else:
        return None, None


async def add_new_speaker_emb(emb: list, redis_client, client_id, speaker_id=None):
    logger.info("Adding new speaker...")
    speaker_id = speaker_id if speaker_id else str(uuid4())
    client.upsert(
        collection_name="main",
        wait=True,
        points=[
            models.PointStruct(id=str(uuid4()), vector=emb, payload={"speaker_id": speaker_id, "client_id": client_id})
        ],
    )
    await redis_client.lpush(keys.EMBEDDINGS, json.dumps((speaker_id, emb.tolist(), client_id)))
    logger.info(f"Added new speaker {speaker_id}")
    return speaker_id


async def process_speaker_emb(emb: list, redis_client, client_id):
    speaker_id, score = get_stored_knn(emb, client_id)
    logger.info(f"score: {score}")

    if speaker_id:
        if score > 0.95:
            pass
        elif score > 0.75:
            await add_new_speaker_emb(emb, redis_client, client_id, speaker_id=speaker_id)
        else:
            speaker_id = await add_new_speaker_emb(emb, redis_client, client_id)
    else:
        speaker_id = await add_new_speaker_emb(emb, redis_client, client_id)

    return str(speaker_id), score


def parse_segment(segment):
    return segment[0].start, segment[0].end, int(segment[-1].split("_")[1])


async def process(redis_client) -> None:
    # spop from diarizer_todo
    # sadd diarizer_doing, 
    # if already there:
    #    pass
    #     
    # else:
    #   if current_timestamp - seek < step:
    #        put back into diarizer_todo
    #        pass
    
    #   else:
    #       find connection that is withing range for seek and better is longer covering step segment
    #       extract audio from seek up to the end of file or max_len which is smaller
    #       process audio and get output
    #       populate DiarizeReady
    #       save iarize_seek into meeting_id hash
    #    
    
    


    try:
        
    
    
        # audio_slicer = await AudioSlicer.from_ffmpeg_slice(path, start, start + max_length)
        # slice_duration = audio_slicer.audio.duration_seconds
        # audio = Audio(audio_name, redis_client)
        
        if await audio.get():
            output, embeddings = pipeline(io.BytesIO(audio.data), return_embeddings=True)
            if len(embeddings) == 0:
                await audio.delete()
        else:
            assert "no audio"

        speakers = [await process_speaker_emb(e, redis_client, client_id) for e in embeddings]
        segments = [i for i in output.itertracks(yield_label=True)]
        df = pd.DataFrame([parse_segment(s) for s in segments], columns=["start", "end", "speaker_id"])
        df["speaker"] = df["speaker_id"].replace({i: s[0] for i, s in enumerate(speakers)})
        df["score"] = df["speaker_id"].replace({i: s[1] for i, s in enumerate(speakers)})
        diarization_data = df.drop(columns=["speaker_id"]).to_dict("records")
        await Diarisation(audio_name, redis_client, diarization_data).save()
        await redis_client.lpush(f"DiarizeReady:{audio_name}", "Done")
        logger.info("done")

    except Exception as ex:
        logger.error(ex)
        await redis_client.rpush('Audio2DiarizeQueue', f'{audio_name}:{client_id}')


async def main():
    redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)

    while True:
        await asyncio.sleep(0.1)
        await process(redis_client)


if __name__ == "__main__":
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token="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",
    )
    pipeline.to(torch.device("cuda"))
    asyncio.run(main())
