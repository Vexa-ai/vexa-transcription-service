import asyncio
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from uuid import uuid4

import pandas as pd
from redis.asyncio.client import Redis

from app.database_redis import keys
from app.database_redis.connection import get_redis_client
from app.services.audio.audio import AudioFileCorruptedError, AudioSlicer
from app.services.audio.redis import (
    Diarisation,
    Diarizer,
    Meeting,
    Transcriber,
    Transcript,
    best_covering_connection,
    connection_with_minimal_start_greater_than_target,
)
from app.settings import settings


@dataclass
class SpeakerEmbs:
    client: Any
    logger: Any = field(default=logging.getLogger(__name__))

    def get_stored_knn(self, emb: list, user_id):
        from qdrant_client import QdrantClient, models

        search_result = self.client.search(
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

    async def add_new_speaker_emb(self, emb: list, redis_client, user_id, speaker_id=None):
        from qdrant_client import QdrantClient, models

        self.logger.info("Adding new speaker...")
        speaker_id = speaker_id if speaker_id else str(uuid4())
        self.client.upsert(
            collection_name="main",
            wait=True,
            points=[
                models.PointStruct(id=str(uuid4()), vector=emb, payload={"speaker_id": speaker_id, "user_id": user_id})
            ],
        )
        await redis_client.lpush(keys.SPEAKER_EMBEDDINGS, json.dumps((speaker_id, emb.tolist(), user_id)))
        self.logger.info(f"Added new speaker {speaker_id}")
        return speaker_id

    async def process_speaker_emb(self, emb: list, redis_client, user_id):
        speaker_id, score = self.get_stored_knn(emb, user_id)
        self.logger.info(f"score: {score}")

        if speaker_id:
            if score > 0.95:
                pass
            elif score > 0.70:
                await self.add_new_speaker_emb(emb, redis_client, user_id, speaker_id=speaker_id)
            else:
                speaker_id = await self.add_new_speaker_emb(emb, redis_client, user_id)
        else:
            speaker_id = await self.add_new_speaker_emb(emb, redis_client, user_id)

        return str(speaker_id), score


def parse_segment(segment):
    return segment[0].start, segment[0].end, int(segment[-1].split("_")[1])


async def get_next_chunk_start(diarization_result, length, shift):
    if len(diarization_result) > 0:
        last_speech = diarization_result[-1]
        ended_silence = length - last_speech["end"]
        if ended_silence < 2:
            return last_speech["start"] + shift
        else:
            return last_speech["end"] + shift
    else:
        return None


@dataclass
class Processor:
    processor_type: Union["transcriber", "diarizer"]
    redis_client: Redis
    logger: Any = field(default=logging.getLogger(__name__))

    def __post_init__(self):
        if self.processor_type == "transcriber":
            self.processor = Transcriber(self.redis_client)
        if self.processor_type == "diarizer":
            self.processor = Diarizer(self.redis_client)

    async def read(self, max_length=240):
        meeting_id = await self.processor.pop_inprogress()

        if not meeting_id:
            self.meeting = None
            return

        self.meeting = Meeting(self.redis_client, meeting_id)
        self.logger.info(f"Meeting ID: {meeting_id}")

        await self.meeting.load_from_redis()

        if isinstance(self.processor, Diarizer):
            self.seek_timestamp = self.meeting.diarizer_seek_timestamp
        else:
            self.seek_timestamp = self.meeting.transcriber_seek_timestamp

        self.logger.info(f"seek_timestamp: {self.seek_timestamp}")
        current_time = datetime.now(timezone.utc)

        self.connections = await self.meeting.get_connections()
        self.logger.info(f"number of connections: {len(self.connections)}")
        self.connection = best_covering_connection(self.seek_timestamp, current_time, self.connections)

        if self.connection:
            self.logger.info(f"Connection ID: {self.connection.id}")

            if self.seek_timestamp < self.connection.start_timestamp:
                self.seek_timestamp = self.connection.start_timestamp

            seek = (self.seek_timestamp - self.connection.start_timestamp).total_seconds()
            self.logger.info(f"seek: {seek}")
            path = f"/audio/{self.connection.id}.webm"

            try:
                audio_slicer = await AudioSlicer.from_ffmpeg_slice(path, seek, max_length)
                self.slice_duration = audio_slicer.audio.duration_seconds
                self.audio_data = await audio_slicer.export_data()
                return True

            except AudioFileCorruptedError:
                self.logger.error(f"Audio file at {path} is corrupted")
                await self.meeting.delete_connection(self.connection.id)
                return

            except Exception:
                self.logger.error(f"could nod read file {path} at seek {seek} with length {max_length}")
                await self.meeting.delete_connection(self.connection.id)
                return

    async def diarize(self, pipeline, qdrant_client):
        client = SpeakerEmbs(qdrant_client)

        output, embeddings = pipeline(io.BytesIO(self.audio_data), return_embeddings=True)
        self.logger.info(len(embeddings))

        if len(embeddings) == 0:
            self.logger.info("No embeddings found, skipping...")

            self.done = False
        else:
            self.logger.info(f"{len(embeddings)} embeddings found")
            speakers = [
                await client.process_speaker_emb(e, self.redis_client, self.connection.user_id) for e in embeddings
            ]

            segments = [i for i in output.itertracks(yield_label=True)]
            df = pd.DataFrame([parse_segment(s) for s in segments], columns=["start", "end", "speaker_id"])
            df["speaker"] = df["speaker_id"].replace({i: s[0] for i, s in enumerate(speakers)})
            df["score"] = df["speaker_id"].replace({i: s[1] for i, s in enumerate(speakers)})
            result = df.drop(columns=["speaker_id"]).to_dict("records")

            diarization = Diarisation(
                self.meeting.meeting_id,
                self.redis_client,
                (result, self.meeting.diarizer_seek_timestamp.isoformat(), self.connection.id),
            )
            await diarization.lpush()
            self.logger.info("pushed")

            self.done = True

    async def transcribe(self, model):
        # ToDo: чтение файла занимает время (~20 сек)
        segments, _ = model.transcribe(
            io.BytesIO(self.audio_data),
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
            vad_parameters={"threshold": 0.9},
        )
        segments = [s for s in list(segments)]
        result = list(segments)
        print(result)
        transcription = Transcript(
            self.meeting.meeting_id,
            self.redis_client,
            (result, self.meeting.transcriber_seek_timestamp.isoformat(), self.connection.id),
        )
        if len(result) > 0:
            await transcription.lpush()
            self.logger.info("pushed")
            self.done = True

        else:
            self.done = False

    async def find_next_seek(self, overlap=0):
        if self.done:
            print(f'[self.done ({self.done})]self.slice_duration: {self.slice_duration}')
            self.seek_timestamp = (
                self.seek_timestamp + pd.Timedelta(seconds=self.slice_duration) - pd.Timedelta(seconds=overlap)
            )
        else:
            next_connection = connection_with_minimal_start_greater_than_target(self.seek_timestamp, self.connections)
            if next_connection:
                self.seek_timestamp = next_connection.start_timestamp
        self.logger.info(f"seek_timestamp: {self.seek_timestamp}")

        if isinstance(self.processor, Diarizer):
            self.meeting.diarizer_seek_timestamp = self.seek_timestamp
        else:
            self.meeting.transcriber_seek_timestamp = self.seek_timestamp

        await self.meeting.update_redis()

    async def do_finally(self):
        if self.meeting:
            await self.processor.remove(self.meeting.meeting_id)
            await self.meeting.update_redis()
