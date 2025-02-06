"""Integration tests for the complete audio processing pipeline."""
import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio.client import Redis

from app.services.audio.audio import AudioSlicer
from app.services.audio.redis import Meeting, Transcriber
from app.services.transcription.matcher import SpeakerMeta, TranscriptSegment
from processor import Processor  # Updated import path


@pytest.fixture
def base_timestamp():
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_redis():
    redis = AsyncMock(spec=Redis)
    
    async def mock_lrange(*args, **kwargs):
        return [
            json.dumps({
                "speaker_name": "speaker1",
                "meta": "1" * 70 + "0" * 30,  # 70% mic activity
                "timestamp": "2024-01-01T12:00:00+00:00",  # UTC timezone
                "speaker_delay_sec": "0.0"
            }),
            json.dumps({
                "speaker_name": "speaker2",
                "meta": "1" * 40 + "0" * 60,  # 40% mic activity
                "timestamp": "2024-01-01T12:00:01+00:00",  # UTC timezone
                "speaker_delay_sec": "0.1"
            })
        ]
    
    async def mock_lpush(*args, **kwargs):
        return 1
    
    redis.lrange = AsyncMock(side_effect=mock_lrange)
    redis.lpush = AsyncMock(side_effect=mock_lpush)
    return redis


@pytest.fixture
def mock_audio_data():
    return b"mock_audio_data"


@pytest.fixture
def mock_transcription_model():
    class MockSegment:
        def __init__(self, text, start, end):
            self.text = text
            self.start = start
            self.end = end

    class MockModel:
        def transcribe(self, audio_data, **kwargs):
            # Return mock segments that would typically come from whisper
            segments = [
                MockSegment("Hello world", 0.0, 1.0),
                MockSegment("This is a test", 1.2, 2.5),
                MockSegment("Final segment", 2.7, 3.5)
            ]
            return segments, None

    return MockModel()


class MockMeeting(Meeting):
    """Mock Meeting class with required attributes."""
    def __init__(self, redis_client, meeting_id):
        super().__init__(redis_client, meeting_id)
        self.transcriber_seek_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    async def load_from_redis(self):
        pass

    async def update_redis(self):
        pass


@pytest.mark.asyncio
async def test_complete_pipeline(mock_redis, base_timestamp, mock_audio_data, mock_transcription_model):
    """Test the complete pipeline from audio processing to transcript generation."""
    # Setup processor with mocked dependencies
    processor = Processor(mock_redis)
    
    # Mock meeting data
    processor.meeting = MockMeeting(mock_redis, "test_meeting")
    processor.seek_timestamp = base_timestamp
    processor.audio_data = mock_audio_data
    processor.slice_duration = 3.5
    processor.connection = MagicMock()
    processor.connection.id = "test_connection"
    
    # Run transcription
    await processor.transcribe(mock_transcription_model)
    
    # Verify Redis interactions
    mock_redis.lrange.assert_called_once()
    mock_redis.lpush.assert_called_once()
    
    # Verify the format of pushed transcripts
    call_args = mock_redis.lpush.call_args[0]
    assert len(call_args) == 2
    key, data = call_args
    
    # Parse the pushed data
    result, timestamp, connection_id = json.loads(data)
    
    # Verify structure and content
    assert len(result) == 3  # Three segments
    for segment in result:
        assert "text" in segment
        assert "start" in segment
        assert "end" in segment
        assert "speaker" in segment
        assert "confidence" in segment
        
        # Verify timestamps are in ISO format
        datetime.fromisoformat(segment["start"])
        datetime.fromisoformat(segment["end"])
        
        # At least one segment should have a speaker assigned
        if segment["speaker"]:
            assert segment["speaker"] in ["speaker1", "speaker2"]
            assert 0 <= segment["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_pipeline_no_speakers(mock_redis, base_timestamp, mock_audio_data, mock_transcription_model):
    """Test pipeline behavior when no speakers are active."""
    # Modify Redis mock to return empty speaker list
    async def mock_empty_lrange(*args, **kwargs):
        return []
    mock_redis.lrange = AsyncMock(side_effect=mock_empty_lrange)
    
    processor = Processor(mock_redis)
    processor.meeting = MockMeeting(mock_redis, "test_meeting")
    processor.seek_timestamp = base_timestamp
    processor.audio_data = mock_audio_data
    processor.slice_duration = 3.5
    processor.connection = MagicMock()
    processor.connection.id = "test_connection"
    
    await processor.transcribe(mock_transcription_model)
    
    # Verify transcripts are generated without speakers
    call_args = mock_redis.lpush.call_args[0]
    result, timestamp, connection_id = json.loads(call_args[1])
    
    for segment in result:
        assert segment["speaker"] is None
        assert segment["confidence"] == 0.0


@pytest.mark.asyncio
async def test_pipeline_with_speaker_delay(mock_redis, base_timestamp, mock_audio_data, mock_transcription_model):
    """Test pipeline handling of speaker delay."""
    # Modify Redis mock to include significant speaker delay
    async def mock_delayed_lrange(*args, **kwargs):
        return [json.dumps({
            "speaker_name": "delayed_speaker",
            "meta": "1" * 80 + "0" * 20,  # 80% mic activity
            "timestamp": "2024-01-01T12:00:00+00:00",  # UTC timezone
            "speaker_delay_sec": "0.5"  # Half second delay
        })]
    mock_redis.lrange = AsyncMock(side_effect=mock_delayed_lrange)
    
    processor = Processor(mock_redis)
    processor.meeting = MockMeeting(mock_redis, "test_meeting")
    processor.seek_timestamp = base_timestamp
    processor.audio_data = mock_audio_data
    processor.slice_duration = 3.5
    processor.connection = MagicMock()
    processor.connection.id = "test_connection"
    
    await processor.transcribe(mock_transcription_model)
    
    # Verify speaker delay is properly handled
    call_args = mock_redis.lpush.call_args[0]
    result, timestamp, connection_id = json.loads(call_args[1])
    
    # The first segment might not have a speaker due to delay
    first_segment = result[0]
    if first_segment["start"] < (base_timestamp + timedelta(seconds=0.5)).isoformat():
        assert first_segment["speaker"] is None
    
    # Later segments should have the speaker assigned
    later_segments = [s for s in result if s["start"] >= (base_timestamp + timedelta(seconds=0.5)).isoformat()]
    assert any(s["speaker"] == "delayed_speaker" for s in later_segments)


@pytest.mark.asyncio
async def test_pipeline_error_handling(mock_redis, base_timestamp, mock_audio_data):
    """Test pipeline error handling with failing transcription."""
    processor = Processor(mock_redis)
    processor.meeting = MockMeeting(mock_redis, "test_meeting")
    processor.seek_timestamp = base_timestamp
    processor.audio_data = mock_audio_data
    processor.slice_duration = 3.5
    processor.connection = MagicMock()
    processor.connection.id = "test_connection"
    
    # Create a model that raises an exception
    class FailingModel:
        def transcribe(self, *args, **kwargs):
            raise Exception("Transcription failed")
    
    # Verify the pipeline handles the error gracefully
    with pytest.raises(Exception) as exc_info:
        await processor.transcribe(FailingModel())
    
    assert str(exc_info.value) == "Transcription failed"
    assert not mock_redis.lpush.called  # No data should be pushed on error 