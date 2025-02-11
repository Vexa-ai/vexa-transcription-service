import io
import json
import logging
import aiohttp
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Union
from uuid import uuid4

import pandas as pd
from redis.asyncio.client import Redis

from app.clients.database_redis import keys
from app.services.audio.audio import AudioFileCorruptedError, AudioSlicer
from app.services.audio.redis import (
    Meeting,
    Transcriber,
    Transcript,
    best_covering_connection,
    connection_with_minimal_start_greater_than_target,
)
from app.services.transcription.matcher import TranscriptSpeakerMatcher, TranscriptSegment, SpeakerMeta


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
    redis_client: Redis
    logger: Any = field(default=logging.getLogger(__name__))
    whisper_service_url: str = field(default_factory=lambda: os.getenv("WHISPER_SERVICE_URL", "https://transcribe.dev.vexa.ai"))
    whisper_api_token: str = field(default_factory=lambda: os.getenv("WHISPER_API_TOKEN", "default_token_change_me"))

    def __post_init__(self):
        self.processor = Transcriber(self.redis_client)
        self.matcher = TranscriptSpeakerMatcher()

    async def read(self, max_length=240):
        meeting_id = await self.processor.pop_inprogress()

        if not meeting_id:
            self.meeting = None
            return

        self.meeting = Meeting(self.redis_client, meeting_id)
        self.logger.info(f"Meeting ID: {meeting_id}")

        await self.meeting.load_from_redis()
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

    async def transcribe(self):
        try:
            headers = {"Authorization": f"Bearer {self.whisper_api_token}"}
            async with aiohttp.ClientSession() as session:
                async with session.post(self.whisper_service_url, data=self.audio_data, headers=headers) as response:
                    if response.status != 200:
                        self.logger.error(f"Whisper service error: {response.status}")
                        if response.status == 401:
                            self.logger.error("Authentication failed - check WHISPER_API_TOKEN")
                        self.done = False
                        return
                    
                    result = await response.json()
                    text = result["transcription"]

                    # Since we don't get word timestamps from the service, we'll create a single segment
                    transcript_segments = [
                        TranscriptSegment(
                            content=text,
                            start_timestamp=self.seek_timestamp,
                            end_timestamp=self.seek_timestamp + pd.Timedelta(seconds=self.slice_duration)
                        )
                    ]

                    # Get speaker activities
                    speaker_activities = await self._get_speaker_activities()

                    # Match speakers to segments
                    matched_segments = self.matcher.match_segments(transcript_segments, speaker_activities)

                    # Prepare for storage
                    result = []
                    for segment in matched_segments:
                        result.append({
                            "text": segment.content,
                            "start": segment.start_timestamp.isoformat(),
                            "end": segment.end_timestamp.isoformat(),
                            "speaker": segment.speaker,
                            "confidence": segment.confidence
                        })

                    if result:
                        transcription = Transcript(
                            self.meeting.meeting_id,
                            self.redis_client,
                            (result, self.meeting.transcriber_seek_timestamp.isoformat(), self.connection.id),
                        )
                        await transcription.lpush()
                        self.logger.info("pushed")
                        self.done = True
                    else:
                        self.done = False

        except Exception as e:
            self.logger.error(f"Error calling whisper service: {str(e)}")
            self.done = False

    async def _get_speaker_activities(self) -> List[SpeakerMeta]:
        """Get speaker activities from the current meeting."""
        # Get raw speaker data from Redis
        raw_data = await self.redis_client.lrange(f"{self.meeting.meeting_id}:speakers", start=0, end=-1)
        speaker_activities = []

        for data in raw_data:
            speaker_data = json.loads(data)
            # Calculate normalized mic level from meta
            mic_level = sum(int(n) for n in speaker_data.get("meta", [])) / 100.0  # Normalize to 0-1
            
            speaker_activities.append(SpeakerMeta(
                name=speaker_data["speaker_name"],
                mic_level=min(mic_level, 1.0),  # Cap at 1.0
                timestamp=datetime.fromisoformat(speaker_data["timestamp"].rstrip("Z")),
                delay_sec=float(speaker_data.get("speaker_delay_sec", 0.0))
            ))

        return speaker_activities

    async def find_next_seek(self, overlap=0):
        if self.done:
            self.seek_timestamp = (
                self.seek_timestamp + pd.Timedelta(seconds=self.slice_duration) - pd.Timedelta(seconds=overlap)
            )
        else:
            next_connection = connection_with_minimal_start_greater_than_target(self.seek_timestamp, self.connections)
            if next_connection:
                self.seek_timestamp = next_connection.start_timestamp
        self.logger.info(f"seek_timestamp: {self.seek_timestamp}")

        self.meeting.transcriber_seek_timestamp = self.seek_timestamp
        await self.meeting.update_redis()

    async def do_finally(self):
        if self.meeting:
            await self.processor.remove(self.meeting.meeting_id)
            await self.meeting.update_redis()
