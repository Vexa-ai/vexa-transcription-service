"""Module for matching transcripts with speakers based on temporal proximity and mic activity."""
from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel


class SpeakerMeta(BaseModel):
    """Speaker metadata with activity information."""
    name: str
    mic_level: float  # Normalized mic level (0-1)
    timestamp: datetime
    delay_sec: float = 0.0


class TranscriptSegment(BaseModel):
    """Transcript segment with matched speaker."""
    content: str
    start_timestamp: datetime
    end_timestamp: datetime
    speaker: Optional[str] = None
    confidence: float = 0.0


class TranscriptSpeakerMatcher:
    """Class for matching transcripts with speakers based on temporal intersection and mic activity."""

    def __init__(self, min_intersection_sec: float = 0.1):
        """Initialize matcher with configurable parameters.
        
        Args:
            min_intersection_sec: Minimum intersection time in seconds (default: 0.1s)
        """
        self.min_intersection_sec = min_intersection_sec
        self.min_intersection_ratio = 0.2  # Require at least 20% overlap

    def match_segments(
        self,
        transcript_segments: List[TranscriptSegment],
        speaker_activities: List[SpeakerMeta]
    ) -> List[TranscriptSegment]:
        """Match transcript segments with speakers using temporal intersection.
        
        Args:
            transcript_segments: List of transcript segments to match
            speaker_activities: List of speaker activities with mic levels
            
        Returns:
            List of transcript segments with matched speakers and confidence scores
        """
        if not speaker_activities or not transcript_segments:
            return transcript_segments

        # Filter out inactive speakers first
        active_speakers = [s for s in speaker_activities if s.mic_level > 0]
        if not active_speakers:
            return transcript_segments

        # Sort speakers by mic level (descending) and timestamp
        active_speakers.sort(key=lambda x: (-x.mic_level, x.timestamp))

        # Process each segment
        result_segments = []
        for segment in transcript_segments:
            best_speaker = None
            max_intersection = timedelta(seconds=0)
            best_confidence = 0.0

            segment_duration = (segment.end_timestamp - segment.start_timestamp).total_seconds()
            min_intersection_sec = min(
                self.min_intersection_sec,
                segment_duration * self.min_intersection_ratio
            )

            for speaker in active_speakers:
                # Apply speaker delay
                speaker_start = speaker.timestamp + timedelta(seconds=speaker.delay_sec)
                # The speaker is active from their timestamp until the end of the segment
                speaker_end = segment.end_timestamp

                # Skip if the speaker starts after the segment ends
                if speaker_start > segment.end_timestamp:
                    continue

                # Skip if the speaker hasn't started speaking yet (considering delay)
                if speaker_start > segment.start_timestamp:
                    continue

                # Calculate intersection
                intersection_start = max(speaker_start, segment.start_timestamp)
                intersection_end = min(speaker_end, segment.end_timestamp)
                intersection = max(timedelta(seconds=0), intersection_end - intersection_start)

                if intersection.total_seconds() > min_intersection_sec:
                    if intersection > max_intersection:
                        max_intersection = intersection
                        best_speaker = speaker
                        best_confidence = min(
                            speaker.mic_level * (intersection.total_seconds() / segment_duration),
                            1.0
                        )

            # Create new segment with matched speaker
            result_segments.append(
                TranscriptSegment(
                    content=segment.content,
                    start_timestamp=segment.start_timestamp,
                    end_timestamp=segment.end_timestamp,
                    speaker=best_speaker.name if best_speaker else None,
                    confidence=best_confidence
                )
            )

        return result_segments 