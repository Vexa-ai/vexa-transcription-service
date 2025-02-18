import io
import json
import logging
import aiohttp
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Union, Optional
from uuid import uuid4

import pandas as pd
import tiktoken
from redis.asyncio.client import Redis

from app.redis_transcribe import keys
from app.services.audio.audio import AudioFileCorruptedError, AudioSlicer
from app.services.audio.redis_models import (
    Meeting,
    Transcriber,
    Transcript,
    TranscriptPrompt,
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
    whisper_service_url: str = field(default_factory=lambda: os.getenv("WHISPER_SERVICE_URL"))
    whisper_api_token: str = field(default_factory=lambda: os.getenv("WHISPER_API_TOKEN"))
    max_length: int = field(default=30)

    def __post_init__(self):
        self.processor = Transcriber(self.redis_client)
        self.matcher = None  # Initialize as None, will be set after we have seek_timestamp
        self.slice_duration = 0  # Initialize slice_duration
        self.tokenizer = tiktoken.get_encoding("gpt2")  # Initialize tokenizer

    async def read(self):
       # self.logger.info("start read")
        meeting_id = await self.processor.pop_inprogress()
      #  self.logger.info(f"meeting_id: {meeting_id}")

        if not meeting_id:
            self.meeting = None
            return

        self.meeting = Meeting(self.redis_client, meeting_id)


        await self.meeting.load_from_redis()
        self.seek_timestamp = self.meeting.transcriber_seek_timestamp
        
        # Initialize matcher with seek_timestamp
        self.matcher = TranscriptSpeakerMatcher(self.seek_timestamp)

        self.logger.info(f"seek_timestamp: {self.seek_timestamp}")
        current_time = datetime.now(timezone.utc)

        self.connections = await self.meeting.get_connections()
        self.logger.info(f"number of connections: {len(self.connections)}")
        self.connection = best_covering_connection(self.seek_timestamp, current_time, self.connections) #should not be current time but instead end seek, which is last seek + accumulated step (so that we add step to accumulated if no overlapping connection)

        if self.connection:
            self.logger.info(f"Connection ID: {self.connection.id}")

            if self.seek_timestamp < self.connection.start_timestamp:
                self.seek_timestamp = self.connection.start_timestamp

            seek = (self.seek_timestamp - self.connection.start_timestamp).total_seconds()
            self.logger.info(f"seek: {seek}")
            path = f"/data/audio/{self.connection.id}.webm"

            try:
                self.audio_slicer = await AudioSlicer.from_ffmpeg_slice(path, seek, self.max_length)
                self.slice_duration = self.audio_slicer.audio.duration_seconds
                self.audio_data = await self.audio_slicer.export_data()
                return True

            except AudioFileCorruptedError:
                self.logger.error(f"Audio file at {path} is corrupted")
                await self.meeting.delete_connection(self.connection.id)
                return

            except Exception:
                self.logger.error(f"could nod read file {path} at seek {seek} with length {self.max_length}")
                await self.meeting.delete_connection(self.connection.id)
                return

    async def transcribe(self):
        try:
            # Get previous prompt if available
            prompt_cache = TranscriptPrompt(self.meeting.meeting_id, self.redis_client)
            initial_prompt = await prompt_cache.get()
            print(initial_prompt)
            self.logger.info(f"Retrieved initial prompt for meeting {self.meeting.meeting_id}: {'Found' if initial_prompt else 'None'}")
            
            # Prepare request payload
            request_data = aiohttp.FormData()
            request_data.add_field('audio_data', 
                                 self.audio_data, 
                                 filename='audio.wav',
                                 content_type='audio/wav')
            
            if initial_prompt:
                request_data.add_field('initial_prompt', initial_prompt)
                self.logger.info(f"Added initial prompt to request (length: {len(initial_prompt)} chars)")
            
            # Call whisper service with prompt
            headers = {"Authorization": f"Bearer {self.whisper_api_token}"}
            self.logger.info(f"Sending request to whisper service: {self.whisper_service_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.whisper_service_url,
                    data=request_data,
                    headers=headers
                ) as response:
                    self.logger.info(f"Whisper service response status: {response.status}")
                    if response.status != 200:
                        self.logger.error(f"Whisper service error: {response.status}")
                        if response.status == 401:
                            self.logger.error("Authentication failed - check WHISPER_API_TOKEN")
                        else:
                            response_text = await response.text()
                            self.logger.error(f"Response content: {response_text}")
                        self.done = False
                        return
                    
                    result = await response.json()
                    self.logger.info(f"Received response with {len(result.get('segments', []))} segments")
                    
                    # Convert whisper segments to TranscriptSegment objects with server timestamp
                    transcription_data = [
                        TranscriptSegment.from_whisper_segment(
                            segment,
                            server_timestamp=(self.meeting.start_server_timestamp.isoformat() if self.meeting.start_server_timestamp else None)
                        )
                        for segment in result['segments']
                    ]
                    self.logger.info(f"Converted {len(transcription_data)} segments to TranscriptSegment objects")
                    
                    # Get speaker data from Redis
                    speaker_data = await self.redis_client.lrange(f"speaker_data", start=0, end=-1)
                    speaker_data = [SpeakerMeta.from_json_data(speaker) for speaker in speaker_data]
                    self.logger.info(f"Retrieved {len(speaker_data)} speaker data entries from Redis")
                    
                    # Match speakers to segments
                    matched_segments = self.matcher.match(speaker_data, transcription_data)
                    self.logger.info(f"Matched {len(matched_segments)} segments with speakers")

                    # Prepare segments for storage
                    result = []
                    transcription_time = datetime.now(timezone.utc).isoformat()
                    for segment in matched_segments:
                        result.append({
                            "content": segment.content,
                            "start_timestamp": segment.start_timestamp,
                            "end_timestamp": segment.end_timestamp,
                            "speaker": segment.speaker,
                            "confidence": segment.confidence,
                            "segment_id": segment.segment_id,
                            "words": segment.words,
                            "server_timestamp": segment.server_timestamp,
                            "transcription_timestamp": transcription_time
                        })

                    if result:
                        # Store transcription result
                        transcription = Transcript(
                            self.meeting.meeting_id,
                            self.redis_client,
                            result
                        )
                        await transcription.lpush()
                        self.logger.info(f"Pushed {len(result)} transcription segments to Redis")
                        
                        try:
                            # Update prompt cache with new content
                            new_text = " ".join(segment["content"] for segment in result)
                            self.logger.info(f"Generated new text for prompt (length: {len(new_text)} chars)")
                            
                            # If we had a previous prompt, append new text
                            if initial_prompt:
                                combined_text = f"{initial_prompt} {new_text}"
                                self.logger.info("Appended new text to existing prompt")
                            else:
                                combined_text = new_text
                                self.logger.info("Using new text as prompt (no previous prompt)")
                                
                            # Tokenize and keep last 400 tokens
                            try:
                                tokens = self.tokenizer.encode(combined_text)
                                self.logger.info(f"Tokenized combined text: {len(tokens)} tokens")
                                
                                if len(tokens) > 400:
                                    tokens = tokens[-400:]
                                    self.logger.info("Truncated to last 400 tokens")
                                    
                                final_text = self.tokenizer.decode(tokens)
                                self.logger.info(f"Final prompt length: {len(final_text)} chars")
                                
                                # Update cache with TTL
                                cache_updated = await prompt_cache.update(final_text)
                                if not cache_updated:
                                    self.logger.warning("Failed to update transcript prompt cache")
                                else:
                                    self.logger.info("Successfully updated prompt cache with TTL")
                            except Exception as e:
                                self.logger.warning(f"Tokenization error: {str(e)}", exc_info=True)
                        except Exception as e:
                            self.logger.warning(f"Error updating prompt cache: {str(e)}", exc_info=True)
                        
                        self.done = True
                    else:
                        self.logger.warning("No segments in result, marking as not done")
                        self.done = False

        except Exception as e:
            self.logger.error(f"Error in transcription process: {str(e)}", exc_info=True)
            self.done = False


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
        # Only proceed with cleanup if we have a meeting
        if not hasattr(self, 'meeting') or self.meeting is None:
          #  self.logger.info("No meeting to process in do_finally")
            return
            
      #  self.logger.info(f"Processing do_finally - slice_duration: {self.slice_duration}, max_length: {self.max_length}, ratio: {self.slice_duration/self.max_length:.2f}")
        
        # if self.slice_duration/self.max_length > 0.5:
        #     self.logger.info(f"Adding to todo - slice duration ratio ({self.slice_duration/self.max_length:.2f}) > 0.9 indicates more audio to process")
        #     await self.processor.add_todo(self.meeting.meeting_id)
        #     print("added to todo")
        # else:
        #self.logger.info(f"Removing from in_progress - slice duration ratio ({self.slice_duration/self.max_length:.2f}) <= 0.9 indicates end of processable audio")
        await self.processor.remove(self.meeting.meeting_id)
    #    print("removed from in_progress")
        await self.meeting.update_redis()
