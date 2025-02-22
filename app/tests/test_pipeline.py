"""Integration tests for the complete audio processing pipeline."""
import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio.client import Redis

from app.services.audio.audio import AudioSlicer
from app.services.audio.redis_models import Meeting, Transcriber
from app.services.transcription.matcher import SpeakerMeta, TranscriptSegment
from app.services.transcription.processor import Processor


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
    class MockModel:
        def transcribe(self, audio_data, **kwargs):
            # Return mock segments in dictionary format
            return [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 1.0,
                    "words": [["Hello", 0.0, 0.5], ["world", 0.5, 1.0]]
                },
                {
                    "text": "This is a test",
                    "start": 1.2,
                    "end": 2.5,
                    "words": [["This", 1.2, 1.4], ["is", 1.4, 1.6], ["a", 1.6, 1.8], ["test", 1.8, 2.5]]
                },
                {
                    "text": "Final segment",
                    "start": 2.7,
                    "end": 3.5,
                    "words": [["Final", 2.7, 3.0], ["segment", 3.0, 3.5]]
                }
            ]

    return MockModel()


class MockMeeting(Meeting):
    """Mock Meeting class with required attributes."""
    def __init__(self, redis_client, meeting_id):
        super().__init__(redis_client, meeting_id)
        self.transcriber_seek_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.start_server_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    async def load_from_redis(self):
        pass

    async def update_redis(self):
        pass


@pytest.fixture
def mock_engine_client():
    return AsyncMock()

@pytest.fixture
def processor(mock_redis, mock_engine_client):
    with patch('app.services.transcription.processor.EngineAPIClient') as mock_engine_api, \
         patch('app.services.transcription.processor.TranscriptQueueManager') as mock_queue_mgr, \
         patch.dict('os.environ', {
             'ENGINE_API_URL': 'http://test-engine-api',
             'ENGINE_API_TOKEN': 'test-token',
             'WHISPER_SERVICE_URL': 'http://test-whisper',
             'WHISPER_API_TOKEN': 'whisper_token'
         }):
        mock_engine_api.return_value = mock_engine_client
        mock_queue_mgr.return_value = AsyncMock()
        return Processor(redis_client=mock_redis)


@pytest.mark.asyncio
async def test_complete_pipeline(processor, mock_redis, base_timestamp, mock_audio_data, mock_transcription_model):
    """Test the complete pipeline from audio processing to transcript generation."""
    # Mock meeting data
    processor.meeting = MockMeeting(mock_redis, "test_meeting")
    processor.seek_timestamp = base_timestamp
    processor.audio_data = mock_audio_data
    processor.slice_duration = 3.5
    processor.connection = MagicMock()
    processor.connection.id = "test_connection"
    processor.matcher = MagicMock()
    processor.matcher.t0 = base_timestamp
    processor.matcher.match = MagicMock(return_value=[TranscriptSegment(
        content="Test content",
        start_timestamp=0.0,
        end_timestamp=1.0,
        speaker="speaker1",
        confidence=0.9,
        segment_id=1,
        words=[["test", 0.0, 1.0]]
    )])
    processor.overlapping_connections = []
    
    # Run transcription with mock model
    await processor.transcribe(mock_transcription_model)
    
    # Verify Redis interactions
    mock_redis.lrange.assert_called_once()
    mock_redis.lpush.assert_called_once()
    
    # Verify the format of pushed transcripts
    call_args = mock_redis.lpush.call_args[0]
    assert len(call_args) == 2
    key, data = call_args
    
    # Parse the pushed data
    result = json.loads(data)
    
    # Verify structure and content
    assert len(result) > 0  # At least one segment
    for segment in result:
        assert "content" in segment
        assert "start_timestamp" in segment
        assert "end_timestamp" in segment
        assert "speaker" in segment
        assert "confidence" in segment
        
        # Verify timestamps are in ISO format
        datetime.fromisoformat(segment["start_timestamp"])
        datetime.fromisoformat(segment["end_timestamp"])
        
        # At least one segment should have a speaker assigned
        if segment["speaker"]:
            assert segment["speaker"] in ["speaker1", "speaker2"]
            assert 0 <= segment["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_pipeline_error_handling(processor, mock_redis, base_timestamp, mock_audio_data):
    """Test pipeline error handling with failing transcription."""
    processor.meeting = MockMeeting(mock_redis, "test_meeting")
    processor.seek_timestamp = base_timestamp
    processor.audio_data = mock_audio_data
    processor.slice_duration = 3.5
    processor.connection = MagicMock()
    processor.connection.id = "test_connection"
    processor.matcher = MagicMock()
    processor.matcher.t0 = base_timestamp
    processor.overlapping_connections = []
    
    # Create a model that raises an exception
    class FailingModel:
        def transcribe(self, *args, **kwargs):
            raise Exception("Transcription failed")
    
    # Verify the pipeline handles the error gracefully
    with pytest.raises(Exception) as exc_info:
        await processor.transcribe(FailingModel())
    
    assert str(exc_info.value) == "Transcription failed"
    assert not mock_redis.lpush.called  # No data should be pushed on error 