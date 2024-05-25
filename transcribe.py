import asyncio
import io
import logging
from datetime import timedelta,datetime,timezone

from faster_whisper import WhisperModel
from app.services.audio.redis import Transcript

from app.database_redis.connection import get_redis_client
from app.services.audio.audio import AudioSlicer
from app.services.audio.redis import Meeting, Transcriber, best_covering_connection
from app.settings import settings

import json

import pandas as pd

logger = logging.getLogger(__name__)


def get_next_seek(result,seek):

    df = pd.DataFrame(json.loads(json.dumps(result)))[[2,3,4]]
    df.columns = ['start','end','speech']
    df['start'] = pd.to_timedelta(df['start'],unit='s') + pd.Timestamp(seek)
    df['end'] = pd.to_timedelta(df['end'],unit='s') + pd.Timestamp(seek)

    if len(result) > 0:
        return df.iloc[-1]['start']

    else:
        return None

        
        

async def process(redis_client, model, max_length=600,overlap = 2) -> None:
    transcriber = Transcriber(redis_client)
    meeting_id = await transcriber.pop_inprogress()

    if not meeting_id:
        return

    meeting = Meeting(redis_client, meeting_id)
    try:
        print(meeting_id)
        await meeting.load_from_redis()
        current_time = datetime.now(timezone.utc)

        connections = await meeting.get_connections()
        connection = best_covering_connection(meeting.diarizer_seek_timestamp, current_time, connections)
        if connection:
            seek = (meeting.diarizer_seek_timestamp - connection.start_timestamp).total_seconds()
            gap =  (meeting.start_timestamp - connection.start_timestamp).total_seconds()
            print('connection.id',connection.id)
            audio_slicer = await AudioSlicer.from_ffmpeg_slice(f"/audio/{connection.id}.webm", seek, max_length)
            slice_duration = audio_slicer.audio.duration_seconds
            audio_data = await audio_slicer.export_data()

            segments, _ = model.transcribe(io.BytesIO(audio_data), beam_size=5, vad_filter=True, word_timestamps=True)
            segments = [s for s in list(segments)]
            logger.info("done")
            result = list(segments)
            print(result)
            transcription = Transcript(meeting_id, redis_client, (result,meeting.diarizer_seek_timestamp.isoformat(),connection.id)) 
            if len(result)>0:
                await transcription.lpush()
                print('pushed')

            meeting.transcriber_seek_timestamp =  (meeting.transcriber_seek_timestamp
                                                   +pd.Timedelta(seconds = slice_duration)
                                                   +pd.Timedelta(seconds = gap)
                                                   -pd.Timedelta(seconds = overlap))
                
            print('meeting.transcriber_seek_timestamp',meeting.transcriber_seek_timestamp)
    except Exception as e:
        print(e)
    finally:
        #TODO: need proper error handling
        await transcriber.remove(meeting.meeting_id)
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
