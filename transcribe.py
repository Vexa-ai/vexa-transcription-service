import asyncio
import io
import logging
from datetime import timedelta, datetime, timezone

from faster_whisper import WhisperModel
from app.services.audio.redis import Transcript

from app.database_redis.connection import get_redis_client
from app.services.audio.audio import AudioSlicer
from app.services.audio.redis import Meeting, Transcriber, best_covering_connection
from app.settings import settings

import json

import pandas as pd

logger = logging.getLogger("transcribe")


def get_next_seek(result, seek):
    df = pd.DataFrame(json.loads(json.dumps(result)))[[2, 3, 4]]
    df.columns = ["start", "end", "speech"]
    df["start"] = pd.to_timedelta(df["start"], unit="s") + pd.Timestamp(seek)
    df["end"] = pd.to_timedelta(df["end"], unit="s") + pd.Timestamp(seek)

    if len(result) > 0:
        return df.iloc[-1]["start"]

    else:
        return None


async def process(redis_client, model, max_length=600, overlap=0) -> None:
    transcriber = Transcriber(redis_client)
    meeting_id = await transcriber.pop_inprogress()

    if not meeting_id:
        return

    meeting = Meeting(redis_client, meeting_id)
    logger.info(f"Meeting ID: {meeting.meeting_id}")
    logger.info(f"transcriber_seek_timestamp: {meeting.transcriber_seek_timestamp}")

    try:
        await meeting.load_from_redis()
        current_time = datetime.now(timezone.utc)

        connections = await meeting.get_connections()
        connection = best_covering_connection(meeting.transcriber_seek_timestamp, current_time, connections)
        if connection:
            logger.info(f"Connection ID: {connection.id}")

            seek = (meeting.transcriber_seek_timestamp - connection.start_timestamp).total_seconds()
            logger.info(f"seek: {seek}")
            gap = (meeting.start_timestamp - connection.start_timestamp).total_seconds()
            logger.info(f"gap: {gap}")
            audio_slicer = await AudioSlicer.from_ffmpeg_slice(f"/audio/{connection.id}.webm", seek, max_length)
            slice_duration = audio_slicer.audio.duration_seconds
            audio_data = await audio_slicer.export_data()

            segments, _ = model.transcribe(
                io.BytesIO(audio_data),
                beam_size=5,
                vad_filter=True,
                word_timestamps=True,
                vad_parameters={"threshold": 0.9},
            )  #
            segments = [s for s in list(segments)]
            logger.info("done")
            result = list(segments)
            print(result)
            transcription = Transcript(
                meeting_id, redis_client, (result, meeting.transcriber_seek_timestamp.isoformat(), connection.id)
            )
            if len(result) > 0:
                await transcription.lpush()
                logger.info("pushed")

            meeting.transcriber_seek_timestamp = (
                meeting.transcriber_seek_timestamp
                + pd.Timedelta(seconds=slice_duration)
                + pd.Timedelta(seconds=gap)
                - pd.Timedelta(seconds=overlap)
            )

            logger.info(f"transcriber_seek_timestamp: {meeting.transcriber_seek_timestamp}")

    except Exception as ex:
        logger.info(ex)

    finally:
        # TODO: need proper error handling
        await transcriber.remove(meeting.meeting_id)
        await meeting.update_redis()


async def main():
    logger.info("Running transcribe loop...")
    redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)

    while True:
        await asyncio.sleep(0.1)
        await process(redis_client, model)


if __name__ == "__main__":
    logger.info("Initialize Model...")
    model_size = "large-v3"
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    logger.info("Model loaded")
    asyncio.run(main())
