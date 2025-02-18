"""Module for matching transcripts with speakers based on temporal proximity and mic activity."""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict
import numpy as np
import pandas as pd
from pydantic import BaseModel
from dataclasses import dataclass, field
import json
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SpeakerMeta(BaseModel):
    """Speaker metadata with activity information."""
    name: str
    mic_level: float  # Normalized mic level (0-1)
    timestamp: datetime
    delay_sec: float = 0.0
    meeting_id: Optional[str] = None
    user_id: Optional[str] = None
    meta_bits: Optional[str] = None  # Store original meta bits for fine-grained analysis

    @classmethod
    def from_json_data(cls, json_str: str) -> 'SpeakerMeta':
        """Create SpeakerMeta from JSON string data
        
        Args:
            json_str: JSON string containing speaker data with fields:
                speaker_name: Name of the speaker
                meta: Binary string representing mic activity
                timestamp: ISO format timestamp
                meeting_id: Meeting identifier
                user_id: User identifier
                speaker_delay_sec: Delay in seconds
                
        Returns:
            SpeakerMeta object with parsed data
        """
        try:
            data = json.loads(json_str)
            
            # Store original meta bits
            meta = data.get('meta', '')
            
            # Calculate mic level from meta binary string
            # Count number of '1's and divide by total length
            mic_level = sum(1 for c in meta if c == '1') / max(len(meta), 1)
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(data['user_timestamp'].rstrip('Z'))
            except (ValueError, AttributeError):
                logger.warning(f"Invalid timestamp format in speaker data: {data.get('user_timestamp')}")
                timestamp = datetime.now(timezone.utc)
            
            return cls(
                name=data['speaker_name'],
                mic_level=mic_level,
                timestamp=timestamp,
                delay_sec=float(data.get('speaker_delay_sec', 0.0)),
                meeting_id=data.get('meeting_id'),
                user_id=data.get('user_id'),
                meta_bits=meta
            )
        except Exception as e:
            logger.error(f"Error parsing speaker data: {e}", exc_info=True)
            raise ValueError(f"Invalid speaker data format: {e}")


def convert_speaker_data(speaker_json_list: List[str]) -> List[SpeakerMeta]:
    """Convert list of speaker JSON strings to SpeakerMeta objects
    
    Args:
        speaker_json_list: List of JSON strings containing speaker data
        
    Returns:
        List of SpeakerMeta objects
    """
    speaker_metas = []
    for json_str in speaker_json_list:
        try:
            speaker_meta = SpeakerMeta.from_json_data(json_str)
            speaker_metas.append(speaker_meta)
        except Exception as e:
            logger.warning(f"Skipping invalid speaker data: {e}")
            continue
    return speaker_metas

@dataclass
class TranscriptSegment:
    """A segment of transcribed speech with timing and speaker information."""
    content: str
    start_timestamp: float  # Start time in seconds relative to audio start
    end_timestamp: float   # End time in seconds relative to audio start
    speaker: Optional[str] = None
    confidence: float = 0.0
    segment_id: Optional[int] = None
    words: List[List[float]] = field(default_factory=list)
    server_timestamp: Optional[str] = None  # ISO format string
    present_user_ids: List[str] = field(default_factory=list)
    partially_present_user_ids: List[str] = field(default_factory=list)

    # Class-level counter for generating unique segment IDs
    _next_segment_id: int = 1

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end_timestamp - self.start_timestamp

    @classmethod
    def from_whisper_segment(cls, segment_data, server_timestamp: Optional[str] = None) -> 'TranscriptSegment':
        """Create TranscriptSegment from Whisper output format.
        
        Args:
            segment_data: Dict containing segment information with fields:
                - start: Start time in seconds
                - end: End time in seconds
                - text: Transcribed text
                - words: Optional word-level information
            server_timestamp: Optional server timestamp
            
        Returns:
            TranscriptSegment with timing information in seconds
        """
        try:
            # Ensure segment_data is a dict
            if not isinstance(segment_data, dict):
                raise ValueError(f"Expected dict, got {type(segment_data)}")
            
            # Extract required fields with proper error handling
            try:
                start = float(segment_data.get("start", 0))
                end = float(segment_data.get("end", 0))
                text = str(segment_data.get("text", ""))
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid segment data format for start/end/text: {e}")
            
            # Generate a new segment ID
            segment_id = cls._next_segment_id
            cls._next_segment_id += 1
            
            # Extract optional fields
            words = segment_data.get("words", [])
            
            # Calculate confidence if word-level info available
            if words and isinstance(words, list):
                try:
                    confidence = sum(word.get("confidence", 0) for word in words) / len(words)
                except (TypeError, AttributeError):
                    confidence = 0.0
            else:
                confidence = 0.0
                
            return cls(
                content=text,
                start_timestamp=start,  # Store as float seconds
                end_timestamp=end,    # Store as float seconds
                confidence=confidence,
                segment_id=segment_id,
                words=words,
                server_timestamp=server_timestamp
            )
        except Exception as e:
            logger.error(f"Error creating TranscriptSegment: {e}", exc_info=True)
            raise ValueError(f"Invalid segment data format: {e}")

class SpeakerSegment:
    """A continuous segment of speaker activity."""
    def __init__(self, speaker: str, start: pd.Timestamp, end: pd.Timestamp, mic_level: float):
        self.speaker = speaker
        self.start = start
        self.end = end
        self.mic_level = mic_level
        
    @property
    def duration(self) -> pd.Timedelta:
        """Get segment duration."""
        return self.end - self.start
        
    def intersection_with(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Timedelta:
        """Calculate temporal intersection with another time range."""
        return pd.Timedelta(seconds=max(0, (
            min(self.end, end) - max(self.start, start)
        ).total_seconds()))

class TranscriptSpeakerMatcher:
    """Class for matching transcripts with speakers based on temporal proximity and mic activity."""
    
    def __init__(self, t0: datetime, min_mic_level: float = 0.0, window_size_sec: float = 5.0, buffer_sec: float = 1.0):
        """Initialize the matcher with configurable parameters."""
        self.min_mic_level = min_mic_level
        self.window_size = pd.Timedelta(seconds=window_size_sec)
        self.buffer = pd.Timedelta(seconds=buffer_sec)
        self.t0 = t0

    def match(self, speaker_data: List[SpeakerMeta], transcription_data: List[TranscriptSegment]) -> List[TranscriptSegment]:
        """Match transcripts with speakers based on temporal proximity and mic activity.
        
        Args:
            speaker_data: List of speaker metadata with activity information
            transcription_data: List of transcript segments to match with speakers
            
        Returns:
            List of transcript segments with matched speakers
        """
        if not speaker_data or not transcription_data:
            return transcription_data  # Return original segments if no speaker data
        
        # Convert speaker data to DataFrame for processing
        speakers_df = pd.DataFrame([{
            'speaker': s.name,
            'mic': s.mic_level,
            'timestamp': s.timestamp,
            'speaker_delay_sec': s.delay_sec
        } for s in speaker_data])

        # Process speaker data
        if len(speakers_df) > 0:
            # Filter by mic level and sort
            speakers_df = speakers_df[speakers_df['mic'] > self.min_mic_level]
            speakers_df = speakers_df.sort_values(['timestamp', 'mic'], ascending=[True, False])
            
            # Apply speaker delay
            speakers_df['timestamp'] = pd.to_datetime(speakers_df['timestamp'], utc=True)
            speakers_df['timestamp'] -= pd.to_timedelta(speakers_df['speaker_delay_sec'], unit='s')
            
            # Group speakers into continuous segments
            speakers_df['change'] = speakers_df['speaker'] != speakers_df['speaker'].shift()
            speakers_df['change'] = speakers_df['change'].cumsum()
            
            diar_df = speakers_df.groupby('change').agg({
                'speaker': 'first',
                'timestamp': ['first', 'last'],
                'mic': 'max'
            }).reset_index(drop=True)
            
            diar_df.columns = ['speaker', 'start', 'end', 'mic']
            
            # Match each transcription segment
            for segment in transcription_data:
                # Convert relative seconds to absolute timestamps
                start_sec = float(segment.start_timestamp)
                end_sec = float(segment.end_timestamp)
                
                segment_start = pd.to_datetime(self.t0) + pd.Timedelta(seconds=start_sec)
                segment_end = pd.to_datetime(self.t0) + pd.Timedelta(seconds=end_sec)
                
                # Calculate intersection with speaker segments
                diar_df['intersection'] = np.maximum(
                    0,
                    np.minimum(diar_df['end'], segment_end) - np.maximum(diar_df['start'], segment_start)
                ).astype('timedelta64[ns]')
                
                # Find best matching speaker
                best_match = diar_df[
                    (diar_df['intersection'] > pd.Timedelta(0))
                ].sort_values(['intersection', 'mic'], ascending=[False, False])
                
                if len(best_match) > 0:
                    segment.speaker = best_match.iloc[0]['speaker']
                    # Set confidence based on intersection ratio and mic level
                    intersection_ratio = best_match.iloc[0]['intersection'] / (segment_end - segment_start)
                    segment.confidence = float(intersection_ratio * best_match.iloc[0]['mic'])
                else:
                    segment.speaker = None
                    segment.confidence = 0.0

        return transcription_data

   