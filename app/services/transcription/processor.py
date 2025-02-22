import io
import json
import logging
import aiohttp
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Union, Optional, Dict
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
    get_timestamps_overlap
)
from app.services.transcription.matcher import TranscriptSpeakerMatcher, TranscriptSegment, SpeakerMeta
from app.services.api.engine_client import EngineAPIClient
from app.services.transcription.queues import TranscriptQueueManager, QueuedTranscript


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
    engine_api_url: str = 'http://host.docker.internal:8010' #field(default_factory=lambda: os.getenv("ENGINE_API_URL")) #TEMP TODO: fix
    engine_api_token: str = field(default_factory=lambda: os.getenv("ENGINE_API_TOKEN"))
    max_length: int = field(default=30)

    def __post_init__(self):
        self.processor = Transcriber(self.redis_client)
        self.matcher = None
        self.slice_duration = 0
        self.tokenizer = tiktoken.get_encoding("gpt2")
        # Initialize engine client with proper timeout and retry settings
        self.engine_client = EngineAPIClient(
            self.engine_api_url,
            self.engine_api_token,
            timeout=30,  # Increase timeout
            max_retries=5  # Increase max retries
        )
        self.queue_manager = TranscriptQueueManager(self.redis_client)
        self._failed_ingestions = {}

    def should_alert_for_failures(self, meeting_id: str) -> bool:
        """
        Check if we should alert for failures based on error count.
        Alerts if there have been 3 or more consecutive failures.
        """
        return self._failed_ingestions.get(meeting_id, 0) >= 3

    async def send_alert(self, message: str):
        """
        Send alert through logging for now.
        This could be extended to send alerts through other channels.
        """
        self.logger.error(f"ALERT: {message}")

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
        
        # Get both best connection and overlapping connections
        connection_result = best_covering_connection(self.seek_timestamp, current_time, self.connections)
        self.connection = connection_result.best_connection
        self.overlapping_connections = connection_result.overlapping_connections
        
        self.logger.info(f"Found {len(self.overlapping_connections)} overlapping connections")
        
        if self.connection:
            self.logger.info(f"Best Connection ID: {self.connection.id}")
            
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
                self.logger.error(f"could not read file {path} at seek {seek} with length {self.max_length}")
                await self.meeting.delete_connection(self.connection.id)
                return

    async def transcribe(self, transcription_model=None):
        """Main transcription orchestration method"""
        try:
            # Log transcription start
            self.logger.info(f"Starting transcription for meeting {self.meeting.meeting_id}")
            self.logger.info(f"Using {'direct model' if transcription_model else 'whisper service'} for transcription")

            # Get raw transcription
            transcription_result = await self._perform_audio_transcription(transcription_model)
            if not transcription_result:
                self.logger.error("Failed to get transcription result")
                self.done = False
                return
            
            self.logger.info(f"Successfully received transcription with {len(transcription_result['segments'])} segments")
            
            # Process and match segments
            matched_segments = await self._process_segments(transcription_result['segments'])
            self.logger.info(f"Processed and matched {len(matched_segments)} segments with speakers")
            
            # Store and queue segments
            success = await self._store_and_queue_segments(matched_segments)
            self.logger.info(f"{'Successfully stored' if success else 'Failed to store'} segments to Redis and queue")
            
            self.done = success
        except Exception as e:
            self.logger.error(f"Error in transcription process: {str(e)}", exc_info=True)
            self.done = False
            raise

    async def _perform_audio_transcription(self, transcription_model=None):
        """Perform actual audio transcription using either direct model or whisper service and update transcription history"""
        # Get previous transcription history if available
        last_transcripts = TranscriptPrompt(self.meeting.meeting_id, self.redis_client)  # TODO: Rename class to TranscriptionHistory
        last_transcripts = await last_transcripts.get()
        self.logger.info(f"Retrieved transcription history for meeting {self.meeting.meeting_id}: {'Found' if last_transcripts else 'None'}")
        
        if transcription_model is not None:
            # Use direct model transcription
            segments = transcription_model.transcribe(self.audio_data)
            result = {"segments": segments}
            self.logger.info(f"Received {len(segments)} segments from direct model transcription")
        else:
            result = await self._call_whisper_service(last_transcripts)
            if not result:
                return None
            
        await self._update_transcription_history(result['segments'])
        
        return result

    async def _call_whisper_service(self, last_transcripts):
        """Call the whisper service to get transcription"""
        request_data = aiohttp.FormData()
        request_data.add_field('audio_data', 
                              self.audio_data, 
                              filename='audio.wav',
                              content_type='audio/wav')
        
        if last_transcripts:
            request_data.add_field('prefix', last_transcripts)
            
        headers = {"Authorization": f"Bearer {self.whisper_api_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.whisper_service_url,
                data=request_data,
                headers=headers
            ) as response:
                if response.status != 200:
                    self.logger.error(f"Whisper service error: {response.status}")
                    if response.status == 401:
                        self.logger.error("Authentication failed - check WHISPER_API_TOKEN")
                    else:
                        response_text = await response.text()
                        self.logger.error(f"Response content: {response_text}")
                    return None
                
                return await response.json()

    async def _process_segments(self, whisper_segments):
        """Process and match segments with speakers and user presence"""
        # Convert to TranscriptSegment objects
        transcription_data = [
            TranscriptSegment.from_whisper_segment(
                segment,
                server_timestamp=(self.meeting.start_server_timestamp.isoformat() 
                                if self.meeting.start_server_timestamp else None)
            )
            for segment in whisper_segments
        ]
        
        # Get and match speaker data
        speaker_data = await self.redis_client.lrange(f"speaker_data", start=0, end=-1)
        speaker_data = [SpeakerMeta.from_json_data(speaker) for speaker in speaker_data]
        matched_segments = self.matcher.match(speaker_data, transcription_data)
        
        # Calculate user presence for each segment
        for segment in matched_segments:
            await self._calculate_user_presence(segment)
        
        return matched_segments

    async def _calculate_user_presence(self, segment):
        """Calculate user presence for a segment"""
        abs_start = pd.to_datetime(self.matcher.t0) + pd.Timedelta(seconds=segment.start_timestamp)
        abs_end = pd.to_datetime(self.matcher.t0) + pd.Timedelta(seconds=segment.end_timestamp)
        segment_duration = (abs_end - abs_start).total_seconds()
        
        present_users = set()
        partially_present = set()
        
        for connection, total_overlap in self.overlapping_connections:
            if not connection.user_id:
                continue
            
            overlap = get_timestamps_overlap(
                abs_start, 
                abs_end,
                connection.start_timestamp,
                connection.end_timestamp
            )
            
            if overlap > 0:
                overlap_ratio = overlap / segment_duration
                if overlap_ratio >= 0.5:
                    present_users.add(connection.user_id)
                else:
                    partially_present.add(connection.user_id)
        
        segment.present_user_ids = list(present_users)
        segment.partially_present_user_ids = list(partially_present)
        segment.start_timestamp = abs_start
        segment.end_timestamp = abs_end

    async def _store_and_queue_segments(self, matched_segments):
        """Store segments in Redis and queue for ingestion"""
        try:
            result = []
            transcription_time = datetime.now(timezone.utc).isoformat()
            
            # Store segments and add to ingestion queue
            for segment in matched_segments:
                segment_data = self._prepare_segment_data(segment, transcription_time)
                result.append(segment_data)
                
                transcript = QueuedTranscript(
                    meeting_id=self.meeting.meeting_id,
                    segment_id=segment.segment_id,
                    content=segment_data
                )
                queued = await self.queue_manager.add_to_ingestion_queue(transcript)
                self.logger.info(
                    f"Segment {segment.segment_id} {'added to' if queued else 'failed to add to'} ingestion queue"
                )
            
            if result:
                # Store in Redis
                transcription = Transcript(
                    self.meeting.meeting_id,
                    self.redis_client,
                    result
                )
                await transcription.lpush()
                self.logger.info(f"Stored {len(result)} segments in Redis cache")
                
                # Process ingestion queue
                self.logger.info("Starting ingestion queue processing")
                await self.process_ingestion_queue()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error storing/queueing segments: {str(e)}", exc_info=True)
            return False

    def _prepare_segment_data(self, segment, transcription_time):
        """Prepare segment data for storage and ingestion"""
        return {
            "content": segment.content,
            "start_timestamp": segment.start_timestamp.isoformat(),
            "end_timestamp": segment.end_timestamp.isoformat(),
            "speaker": segment.speaker,
            "confidence": segment.confidence,
            "segment_id": segment.segment_id,
            "words": segment.words,
            "server_timestamp": segment.server_timestamp,
            "transcription_timestamp": transcription_time,
            "present_user_ids": segment.present_user_ids,
            "partially_present_user_ids": segment.partially_present_user_ids
        }

    async def _update_transcription_history(self, raw_segments):
        """Update the transcription history with raw transcription segments"""
        try:
            transcription_history = TranscriptPrompt(self.meeting.meeting_id, self.redis_client)
            last_transcripts = await transcription_history.get()
            
            # Extract text from the list format segments
            new_text = " ".join(segment[4] if len(segment) > 4 else "" for segment in raw_segments)
            self.logger.info(f"Generated new text for history from raw segments (length: {len(new_text)} chars)")
            
            combined_text = f"{last_transcripts} {new_text}" if last_transcripts else new_text
            
            tokens = self.tokenizer.encode(combined_text)
            if len(tokens) > 400:
                tokens = tokens[-400:]
                self.logger.info("Truncated history to last 400 tokens")
            final_text = self.tokenizer.decode(tokens)
            
            await transcription_history.update(final_text)
            self.logger.info(f"Successfully updated transcription history with {len(final_text)} chars")
        except Exception as e:
            self.logger.warning(f"Error updating transcription history: {str(e)}", exc_info=True)

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

    async def process_transcript(
        self,
        meeting_id: str,
        segment_id: int,
        content: Dict[str, Any]
    ) -> bool:
        """
        Process a single transcript segment by adding it to the ingestion queue.
        
        Args:
            meeting_id: The ID of the meeting
            segment_id: The ID of the segment
            content: The transcript segment content
            
        Returns:
            bool: True if successfully added to queue, False otherwise
        """
        transcript = QueuedTranscript(
            meeting_id=meeting_id,
            segment_id=segment_id,
            content=content
        )
        return await self.queue_manager.add_to_ingestion_queue(transcript)

    async def process_ingestion_queue(self) -> None:
        """Process segments from the ingestion queue"""
        processed_count = 0
        retry_count = 0
        
        while True:
            transcript = await self.queue_manager.get_next_for_ingestion()
            if not transcript:
                break
                
            try:
                self.logger.info(f"Processing segment {transcript.segment_id} from ingestion queue")
                success = await self.engine_client.ingest_transcript_segments(
                    external_id=transcript.meeting_id,
                    segments=[transcript.content]
                )
                
                if success:
                    await self.queue_manager.confirm_processed(transcript)
                    processed_count += 1
                    self.logger.info(f"Successfully ingested segment {transcript.segment_id}")
                else:
                    await self.queue_manager.add_to_retry_queue(
                        transcript,
                        "Engine API ingestion failed"
                    )
                    retry_count += 1
                    self.logger.warning(f"Failed to ingest segment {transcript.segment_id}, added to retry queue")
                    
            except Exception as e:
                await self.queue_manager.add_to_retry_queue(
                    transcript,
                    f"Error ingesting transcript: {str(e)}"
                )
                retry_count += 1
                self.logger.error(f"Error processing segment {transcript.segment_id}: {str(e)}")
        
        self.logger.info(f"Finished processing ingestion queue. Processed: {processed_count}, Retries: {retry_count}")

    async def get_queue_stats(self) -> Dict[str, int]:
        """
        Get statistics about the current state of all queues.
        
        Returns:
            Dict containing counts for each queue
        """
        return await self.queue_manager.get_queue_stats()
