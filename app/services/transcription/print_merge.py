"""Module for merging and displaying transcription with speaker data."""
if __name__ == "__main__" and __package__ is None:
    import sys
    from os import path
    sys.path.insert(0, str(path.abspath(path.join(path.dirname(__file__), "../../.."))))
    __package__ = "app.services.transcription"

from typing import Dict, List, Tuple
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import pandas as pd

from app.services.transcription.matcher import (
    TranscriptSegment,
    SpeakerMeta,
    TranscriptSpeakerMatcher,
    convert_speaker_data
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS.mmm"""
    minutes = int(seconds // 60)
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:06.3f}"

def load_mock_data(file_path: str = None) -> Dict:
    """Load mock data from JSON file.
    
    If no file_path is provided, loads from the project root 'mock_data.json'.
    """
    if file_path is None:
        file_path = str(Path(__file__).resolve().parents[3] / "mock_data.json")
    logger.info(f"Loading mock data from {file_path}")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Mock data file not found at {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    required_keys = ["transcription_segments", "speaker_data"]
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        raise ValueError(f"Mock data is missing required keys: {missing_keys}")
    logger.info(f"Loaded mock data with {len(data['transcription_segments'])} segments and {len(data['speaker_data'])} speaker entries")
    return data

class MockSpeechDAL:
    """Mock data access layer for testing."""
    def __init__(self, mock_data: Dict):
        self.mock_data = mock_data
    
    async def get_all_speakers(self, meeting_id: str) -> List[Dict]:
        """Get all speaker data."""
        # Create a single speaker data entry since we know it's a single speaker case
        speaker_data = {
            "speaker_name": "Speaker1",
            "meta": "1" * 100,  # Indicate active mic
            "timestamp": datetime.fromtimestamp(
                self.mock_data["transcription_segments"][0][2], 
                tz=timezone.utc
            ).isoformat(),
            "speaker_delay_sec": 0.0,
            "meeting_id": meeting_id,
            "user_id": "user1"
        }
        return [speaker_data]
    
    async def get_all_transcriptions(self, meeting_id: str) -> List[Tuple]:
        """Get all transcription data."""
        # Return transcription data in the expected format: List[Tuple[List, str, str]]
        # where each tuple contains (segments, seek_timestamp, connection_id)
        segments = self.mock_data["transcription_segments"]
        seek_timestamp = datetime.fromtimestamp(
            segments[0][2], 
            tz=timezone.utc
        ).isoformat()
        connection_id = "mock_connection"
        return [(segments, seek_timestamp, connection_id)]

async def merge_and_print(mock_data: Dict) -> str:
    """Merge transcription with speaker data and format for display with analytics."""
    # Create mock DAL
    speech_dal = MockSpeechDAL(mock_data)
    
    # Match speakers to segments using the matcher with custom parameters
    matcher = TranscriptSpeakerMatcher(
        min_mic_level=0.05,  # Lower threshold for mic activity
        window_size_sec=10.0,  # Larger window for grouping
        buffer_sec=2.0        # Larger buffer around segments
    )
    matched_df, _ = await matcher.match_transcripts("mock_meeting_id", speech_dal)
    
    if matched_df.empty:
        return "No matched segments found."
    
    # Format output
    output = []
    output.append("=== Transcription Analytics ===\n")
    
    # Calculate analytics
    total_segments = len(matched_df)
    unmatched_segments = matched_df["speaker"].isna().sum()
    total_duration = (matched_df["end"] - matched_df["start"]).total_seconds()
    unmatched_duration = matched_df[matched_df["speaker"].isna()].apply(
        lambda x: (x["end"] - x["start"]).total_seconds(), axis=1
    ).sum()
    
    output.append(f"Total Segments: {total_segments}")
    output.append(f"Unmatched Segments: {unmatched_segments} ({(unmatched_segments/total_segments)*100:.1f}%)")
    output.append(f"Total Duration: {format_timestamp(total_duration)}")
    output.append(f"Unmatched Duration: {format_timestamp(unmatched_duration)} ({(unmatched_duration/total_duration)*100:.1f}%)")
    output.append("\n=== Detailed Segment Analysis ===\n")
    
    # Track segments for context
    segments = matched_df.to_dict("records")
    prev_segment = None
    next_segment_idx = 1
    
    for i, segment in enumerate(segments):
        # Get next segment for context
        next_segment = segments[next_segment_idx] if next_segment_idx < len(segments) else None
        next_segment_idx += 1
        
        # Format timestamps
        start_time = format_timestamp((segment["start"] - pd.Timestamp("1970-01-01", tz=timezone.utc)).total_seconds())
        end_time = format_timestamp((segment["end"] - pd.Timestamp("1970-01-01", tz=timezone.utc)).total_seconds())
        duration = (segment["end"] - segment["start"]).total_seconds()
        
        # Format speaker info
        speaker_info = f"[{segment['speaker']}]" if pd.notna(segment["speaker"]) else "[Unknown Speaker]"
        
        # Build segment header
        segment_header = (
            f"Time: {start_time} - {end_time} (duration: {duration:.2f}s)\n"
            f"Speaker: {speaker_info}\n"
            f"Content: {segment['speech']}\n"
        )
        output.append(segment_header)
        
        # For unmatched segments, add debug info
        if pd.isna(segment["speaker"]):
            output.append("DEBUG INFO FOR UNMATCHED SEGMENT:")
            output.append(f"Segment duration: {duration:.2f}s")
            
            # Show context from surrounding segments
            output.append("\nSurrounding context:")
            if prev_segment:
                prev_speaker = prev_segment["speaker"] if pd.notna(prev_segment["speaker"]) else "Unknown"
                output.append(f"Previous: {prev_speaker} - {prev_segment['speech']}")
            if next_segment:
                next_speaker = next_segment["speaker"] if pd.notna(next_segment["speaker"]) else "Unknown"
                output.append(f"Next: {next_speaker} - {next_segment['speech']}")
            output.append("")
        
        output.append("-" * 80 + "\n")
        prev_segment = segment
    
    return "\n".join(output)

if __name__ == "__main__":
    import asyncio
    
    async def main():
        try:
            # Load mock data and display merged result
            mock_data = load_mock_data()
            result = await merge_and_print(mock_data)
            print(result)
        except Exception as e:
            logger.error(f"Error processing mock data: {e}", exc_info=True)
            print(f"Error: {e}")
    
    asyncio.run(main()) 