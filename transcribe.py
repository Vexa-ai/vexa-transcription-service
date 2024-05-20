import asyncio
import io
import logging
from datetime import timedelta

from faster_whisper import WhisperModel
from app.services.audio.redis import Transcript

from app.database_redis.connection import get_redis_client
from app.services.audio.audio import AudioSlicer
from app.services.audio.redis import Meeting, Transcriber, best_covering_connection
from app.settings import settings

logger = logging.getLogger(__name__)

# TODO: implement recurrent prompt from last item


async def process(redis_client, model, max_length=240) -> None:
    transcriber = Transcriber(redis_client)
    meeting_id = await transcriber.pop_inprogress()

    if not meeting_id:
        return

    meeting = Meeting(redis_client, meeting_id)
    await meeting.load_from_redis()
    seek = meeting.transcribe_seek_timestamp - meeting.start_timestamp

    connection = best_covering_connection(seek, meeting.start_timestamp, meeting.get_connections())
    audio_slicer = await AudioSlicer.from_ffmpeg_slice(f"/audio/{connection.id}.webm", seek, seek + max_length)
    audio_data = await audio_slicer.export_data()

    segments, _ = model.transcribe(io.BytesIO(audio_data), beam_size=5, vad_filter=True, word_timestamps=True)
    segments = [s for s in list(segments)]
    logger.info("done")
    result = [[w._asdict() for w in s.words] for s in segments]
    transcription = Transcript(meeting_id, redis_client, result)
    await transcription.lpush()
    end_of_last_speech = timedelta(seconds=result[-1][-1]["end"])

    meeting.transcribe_seek_timestamp = end_of_last_speech + meeting.transcribe_seek_timestamp
    await transcriber.remove(meeting.id)
    await meeting.update_redis()


async def main():
    redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)

    while True:
        await asyncio.sleep(0.1)
        await process(redis_client, model)


if __name__ == "__main__":
    model_size = "large-v3"
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    logger.info("Model loaded")
    asyncio.run(main())
