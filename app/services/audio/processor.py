import asyncio
import json
import logging
import uuid

from app.database_redis.connection import get_redis_client
from app.services.apis.streamqueue_service.client import StreamQueueServiceAPI
from app.services.audio.audio import AudioSlicer
from app.services.audio.redis import Audio, Diarisation, Transcript
from app.settings import settings

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        self.__running_tasks = set()
        self.__stream_queue_service_api = StreamQueueServiceAPI()

    async def process_connections(self):
        redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
        connections = await self.__stream_queue_service_api.get_connections()
        connection_ids = [c[0] for c in connections]

        for connection_id in connection_ids:
            if connection_id not in self.__running_tasks:
                logger.info(connection_id)

                try:
                    self.__running_tasks.add(connection_id)
                    logger.info(f"running_tasks: {self.__running_tasks}")
                    task = asyncio.create_task(self.__process_connection_task(connection_id, redis_client))
                    task.add_done_callback(lambda t, cid=connection_id: asyncio.create_task(self.__complete_task(cid)))

                except Exception as ex:
                    logger.error(f"Error processing connection {connection_id}: {ex}")
                    self.__running_tasks.remove(connection_id)

    async def __process_connection_task(self, connection_id, redis_client, step=60, max_length=240):
        self.__running_tasks.add(connection_id)
        path = f"/audio/{connection_id}.webm"
        start = await redis_client.rpop(f"Start:{connection_id}")
        start = float(start) if start else 0
        logger.info("started at ", start)

        connection_meta = await self.__writestream2file(connection_id)
        if connection_meta:
            meeting_id, start_timestamp, finish_timestamp, client_id = connection_meta

        audio_slicer = await AudioSlicer.from_ffmpeg_slice(path, start, start + max_length)
        slice_duration = audio_slicer.audio.duration_seconds
        logger.info("slice duaration ", slice_duration)

        if slice_duration > step:

            audio_data = await audio_slicer.export_data()
            audio_name = str(uuid.uuid4())
            audio = Audio(chunk_name=audio_name, redis_client=redis_client, data=audio_data)
            await audio.save()

            while True:
                try:
                    logger.info("gathering results from diarize and transcribe")
                    diarization_result, transcription_result = await asyncio.gather(
                        asyncio.wait_for(self.__diarize(audio_name, redis_client, client_id), timeout=60),
                        asyncio.wait_for(self.__transcribe(audio_name, redis_client, client_id), timeout=60),
                    )

                    await audio.delete()
                except asyncio.TimeoutError:
                    logger.info("A task has timed out")
                except Exception as e:
                    logger.info(e)
                else:
                    logger.info("processing finished", connection_id)

                    await redis_client.lpush(
                        f"Segments",
                        json.dumps(
                            (
                                meeting_id,
                                diarization_result,
                                transcription_result,
                                start,
                                start_timestamp,
                                finish_timestamp,
                            )
                        ),
                    )
                    logger.info("finished segment", connection_id)

                    start_ = await self.__get_next_chunk_start(diarization_result, slice_duration, start)
                    start = start_ if start_ else start + slice_duration
                    logger.info("start")
                    await redis_client.lpush(f"Start:{connection_id}", start)

                    break
        else:
            await redis_client.lpush(f"Start:{connection_id}", start)

    @staticmethod
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

    @staticmethod
    async def __transcribe(audio_name, redis_client, client_id):
        await redis_client.lpush("Audio2TranscribeQueue", f"{audio_name}:{client_id}")
        _, done = await redis_client.brpop(f"TranscribeReady:{audio_name}", timeout=60)
        transcription = Transcript(audio_name, redis_client)
        await transcription.get()
        return transcription.data

    @staticmethod
    async def __diarize(audio_name, redis_client, client_id):
        await redis_client.lpush("Audio2DiarizeQueue", f"{audio_name}:{client_id}")
        _, done = await redis_client.brpop(f"DiarizeReady:{audio_name}", timeout=60)
        diarization = Diarisation(audio_name, redis_client)
        await diarization.get()
        return diarization.data

    async def __writestream2file(self, connection_id):
        path = f"/audio/{connection_id}.webm"
        first_timestamp = None
        items = await self.__stream_queue_service_api.fetch_chunks(connection_id, num_chunks=100)

        if items:
            for item in items["chunks"]:
                chunk = bytes.fromhex(item["chunk"])
                first_timestamp = item["timestamp"] if not first_timestamp else first_timestamp

                # Open the file in append mode
                with open(path, "ab") as file:
                    # Write data to the file
                    file.write(chunk)

                last_timestamp = item["timestamp"]
                meeting_id = item["meeting_id"]
                client_id = item["client_id"]

            return meeting_id, first_timestamp, last_timestamp, client_id

    async def __complete_task(self, connection_id) -> None:
        if connection_id in self.__running_tasks:
            self.__running_tasks.remove(connection_id)

        logger.info(f"Task for {connection_id} completed")
