import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
from app.services.transcription.processor import Processor
from app.services.transcription.queues import QueuedTranscript
from app.services.transcription.matcher import TranscriptSegment

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def mock_engine_client():
    return AsyncMock()

@pytest.fixture
def mock_queue_manager():
    manager = AsyncMock()
    # Set up async return values for queue manager methods
    manager.add_to_ingestion_queue = AsyncMock(return_value=True)
    manager.get_next_for_ingestion = AsyncMock(return_value=None)
    manager.confirm_processed = AsyncMock()
    manager.add_to_retry_queue = AsyncMock()
    manager.get_queue_stats = AsyncMock(return_value={
        'ingestion_queue': 5,
        'retry_queue': 3,
        'failed_queue': 2
    })
    return manager

@pytest.fixture
def processor(mock_redis, mock_engine_client, mock_queue_manager):
    with patch('app.services.transcription.processor.EngineAPIClient') as mock_engine_api, \
         patch('app.services.transcription.processor.TranscriptQueueManager') as mock_queue_mgr, \
         patch.dict('os.environ', {
             'ENGINE_API_URL': 'http://test-engine-api',
             'ENGINE_API_TOKEN': 'test-token',
             'WHISPER_SERVICE_URL': 'http://test-whisper',
             'WHISPER_API_TOKEN': 'whisper_token'
         }):
        mock_engine_api.return_value = mock_engine_client
        mock_queue_mgr.return_value = mock_queue_manager
        return Processor(redis_client=mock_redis)

@pytest.fixture
def test_transcript_data():
    return {
        "content": "Test content",
        "start_timestamp": "2024-03-13T15:32:42.170000+00:00",
        "end_timestamp": "2024-03-13T15:32:45.170000+00:00",
        "confidence": 0.95,
        "segment_id": 1,
        "words": [["test", 0.0, 1.0]],
        "speaker": "Speaker 1",
        "server_timestamp": "2024-03-13T15:32:42.170000+00:00",
        "transcription_timestamp": "2024-03-13T15:32:42.170000+00:00",
        "present_user_ids": [],
        "partially_present_user_ids": []
    }

@pytest.mark.asyncio
async def test_process_transcript(processor, mock_queue_manager, test_transcript_data):
    # Test successful processing
    mock_queue_manager.add_to_ingestion_queue.return_value = True
    result = await processor.process_transcript(
        meeting_id="test-meeting",
        segment_id=1,
        content=test_transcript_data
    )
    assert result is True
    mock_queue_manager.add_to_ingestion_queue.assert_called_once()
    
    # Test failed queue addition
    mock_queue_manager.add_to_ingestion_queue.return_value = False
    result = await processor.process_transcript(
        meeting_id="test-meeting",
        segment_id=1,
        content=test_transcript_data
    )
    assert result is False

@pytest.mark.asyncio
async def test_process_ingestion_queue(processor, mock_queue_manager, mock_engine_client, test_transcript_data):
    # Create test transcript
    test_transcript = QueuedTranscript(
        meeting_id="test-meeting",
        segment_id=1,
        content=test_transcript_data
    )
    
    # Test successful ingestion
    mock_queue_manager.get_next_for_ingestion.side_effect = [test_transcript, None]
    mock_engine_client.ingest_transcript_segments.return_value = True
    
    await processor.process_ingestion_queue()
    
    mock_engine_client.ingest_transcript_segments.assert_called_once_with(
        external_id="test-meeting",
        segments=[test_transcript_data]
    )
    mock_queue_manager.confirm_processed.assert_called_once_with(test_transcript)
    
    # Test failed ingestion
    mock_queue_manager.get_next_for_ingestion.side_effect = [test_transcript, None]
    mock_engine_client.ingest_transcript_segments.return_value = False
    
    await processor.process_ingestion_queue()
    
    mock_queue_manager.add_to_retry_queue.assert_called_with(
        test_transcript,
        "Engine API ingestion failed"
    )
    
    # Test exception handling
    mock_queue_manager.get_next_for_ingestion.side_effect = [test_transcript, None]
    mock_engine_client.ingest_transcript_segments.side_effect = Exception("API error")
    
    await processor.process_ingestion_queue()
    
    mock_queue_manager.add_to_retry_queue.assert_called_with(
        test_transcript,
        "Error ingesting transcript: API error"
    )

@pytest.mark.asyncio
async def test_get_queue_stats(processor, mock_queue_manager):
    expected_stats = {
        'ingestion_queue': 5,
        'retry_queue': 3,
        'failed_queue': 2
    }
    mock_queue_manager.get_queue_stats.return_value = expected_stats
    
    stats = await processor.get_queue_stats()
    assert stats == expected_stats
    mock_queue_manager.get_queue_stats.assert_called_once()

@pytest.fixture
def test_segments():
    return [
        {
            "content": "Test content 1",
            "start_timestamp": "2024-03-13T15:32:42.170000+00:00",
            "end_timestamp": "2024-03-13T15:32:45.170000+00:00",
            "confidence": 0.95,
            "segment_id": 1,
            "words": [["test", 0.0, 1.0]],
            "speaker": "Speaker 1",
            "server_timestamp": "2024-03-13T15:32:42.170000+00:00",
            "transcription_timestamp": "2024-03-13T15:32:42.170000+00:00",
            "present_user_ids": [],
            "partially_present_user_ids": []
        }
    ]

@pytest.mark.asyncio
async def test_successful_engine_ingestion(processor, mock_engine_client, test_segments):
    # Mock successful ingestion
    mock_engine_client.ingest_transcript_segments.return_value = True
    
    # Mock meeting and other required attributes
    processor.meeting = AsyncMock()
    processor.meeting.meeting_id = "test-meeting"
    processor.meeting.start_server_timestamp = datetime.now(timezone.utc)
    
    # Mock audio data and matcher
    processor.audio_data = b"mock_audio_data"
    processor.matcher = AsyncMock()
    processor.matcher.t0 = datetime.now(timezone.utc)
    processor.matcher.match = MagicMock(return_value=[TranscriptSegment(
        content="Test content",
        start_timestamp=0.0,
        end_timestamp=1.0,
        speaker="speaker1",
        confidence=0.9,
        segment_id=1,
        words=[["test", 0.0, 1.0]]
    )])
    
    # Mock overlapping connections
    processor.overlapping_connections = []
    
    # Create a list to store post calls
    post_calls = []
    
    # Create a function that returns a new post context manager for each call
    def create_post_cm(*args, **kwargs):
        mock_post = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"segments": test_segments})
        mock_post.__aenter__.return_value = mock_response
        post_calls.append(mock_post)
        return mock_post
    
    # Mock session context managers
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = AsyncMock(post=create_post_cm)
    
    with patch('aiohttp.ClientSession', return_value=mock_session), \
         patch('app.services.audio.redis_models.Transcript.lpush') as mock_lpush, \
         patch('app.services.transcription.matcher.TranscriptSegment.from_whisper_segment', return_value=TranscriptSegment(
             content="Test content",
             start_timestamp=0.0,
             end_timestamp=1.0,
             speaker="speaker1",
             confidence=0.9,
             segment_id=1,
             words=[["test", 0.0, 1.0]]
         )):
        await processor.transcribe()
        
        # Verify post context manager was entered
        assert len(post_calls) == 1
        assert post_calls[0].__aenter__.called
        
        # Verify Redis storage
        mock_lpush.assert_called_once()
        
        # Verify engine API call
        mock_engine_client.ingest_transcript_segments.assert_called_once_with(
            external_id="test-meeting",
            external_id_type="GOOGLE_MEET",
            segments=[test_segments[0]]
        )
        
        # Verify failed ingestion counter was reset
        assert processor._failed_ingestions.get("test-meeting", 0) == 0

@pytest.mark.asyncio
async def test_failed_engine_ingestion(processor, mock_engine_client, test_segments):
    # Mock failed ingestion
    mock_engine_client.ingest_transcript_segments.return_value = False
    
    # Mock meeting and other required attributes
    processor.meeting = AsyncMock()
    processor.meeting.meeting_id = "test-meeting"
    processor.meeting.start_server_timestamp = datetime.now(timezone.utc)
    
    # Mock audio data and matcher
    processor.audio_data = b"mock_audio_data"
    processor.matcher = AsyncMock()
    processor.matcher.t0 = datetime.now(timezone.utc)
    processor.matcher.match = MagicMock(return_value=[TranscriptSegment(
        content="Test content",
        start_timestamp=0.0,
        end_timestamp=1.0,
        speaker="speaker1",
        confidence=0.9,
        segment_id=1,
        words=[["test", 0.0, 1.0]]
    )])
    
    # Mock overlapping connections
    processor.overlapping_connections = []
    
    # Create a list to store post calls
    post_calls = []
    
    # Create a function that returns a new post context manager for each call
    def create_post_cm(*args, **kwargs):
        mock_post = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"segments": test_segments})
        mock_post.__aenter__.return_value = mock_response
        post_calls.append(mock_post)
        return mock_post
    
    # Mock session context managers
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = AsyncMock(post=create_post_cm)
    
    with patch('aiohttp.ClientSession', return_value=mock_session), \
         patch('app.services.audio.redis_models.Transcript.lpush') as mock_lpush, \
         patch('app.services.transcription.matcher.TranscriptSegment.from_whisper_segment', return_value=TranscriptSegment(
             content="Test content",
             start_timestamp=0.0,
             end_timestamp=1.0,
             speaker="speaker1",
             confidence=0.9,
             segment_id=1,
             words=[["test", 0.0, 1.0]]
         )):
        await processor.transcribe()
        
        # Verify post context manager was entered
        assert len(post_calls) == 1
        assert post_calls[0].__aenter__.called
        
        # Verify Redis storage still happened
        mock_lpush.assert_called_once()
        
        # Verify engine API call
        mock_engine_client.ingest_transcript_segments.assert_called_once_with(
            external_id="test-meeting",
            external_id_type="GOOGLE_MEET",
            segments=[test_segments[0]]
        )
        
        # Verify failed ingestion counter was incremented
        assert processor._failed_ingestions.get("test-meeting", 0) == 1

@pytest.mark.asyncio
async def test_alert_on_multiple_failures(processor, mock_engine_client, test_segments):
    # Mock failed ingestion
    mock_engine_client.ingest_transcript_segments.return_value = False
    
    # Mock meeting and other required attributes
    processor.meeting = AsyncMock()
    processor.meeting.meeting_id = "test-meeting"
    processor.meeting.start_server_timestamp = datetime.now(timezone.utc)
    
    # Mock audio data and matcher
    processor.audio_data = b"mock_audio_data"
    processor.matcher = AsyncMock()
    processor.matcher.t0 = datetime.now(timezone.utc)
    processor.matcher.match = MagicMock(return_value=[TranscriptSegment(
        content="Test content",
        start_timestamp=0.0,
        end_timestamp=1.0,
        speaker="speaker1",
        confidence=0.9,
        segment_id=1,
        words=[["test", 0.0, 1.0]]
    )])
    
    # Mock overlapping connections
    processor.overlapping_connections = []
    
    # Create a list to store post calls
    post_calls = []
    
    # Create a function that returns a new post context manager for each call
    def create_post_cm(*args, **kwargs):
        mock_post = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"segments": [
            {
                "text": "Test content",
                "start": 0.0,
                "end": 1.0,
                "words": [["test", 0.0, 1.0]]
            }
        ]})
        mock_post.__aenter__.return_value = mock_response
        post_calls.append(mock_post)
        return mock_post
    
    # Mock session context managers
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = AsyncMock(post=create_post_cm)
    
    with patch('aiohttp.ClientSession', return_value=mock_session), \
         patch('app.services.audio.redis_models.Transcript.lpush'), \
         patch('app.services.transcription.matcher.TranscriptSegment.from_whisper_segment', return_value=TranscriptSegment(
             content="Test content",
             start_timestamp=0.0,
             end_timestamp=1.0,
             speaker="speaker1",
             confidence=0.9,
             segment_id=1,
             words=[["test", 0.0, 1.0]]
         )):
        for _ in range(3):  # Three failures should trigger alert
            await processor.transcribe()
            
            # Verify each post context manager was entered
            assert len(post_calls) > 0
            for post in post_calls:
                assert post.__aenter__.called
        
        # Verify alert was triggered
        assert processor.should_alert_for_failures("test-meeting") is True
        assert processor._failed_ingestions["test-meeting"] == 3

@pytest.mark.asyncio
async def test_reset_failures_on_success(processor, mock_engine_client, test_segments):
    # Set initial failed state
    processor._failed_ingestions["test-meeting"] = 2
    
    # Mock successful ingestion
    mock_engine_client.ingest_transcript_segments.return_value = True
    
    # Mock meeting and other required attributes
    processor.meeting = AsyncMock()
    processor.meeting.meeting_id = "test-meeting"
    processor.meeting.start_server_timestamp = datetime.now(timezone.utc)
    
    # Mock audio data and matcher
    processor.audio_data = b"mock_audio_data"
    processor.matcher = AsyncMock()
    processor.matcher.t0 = datetime.now(timezone.utc)
    processor.matcher.match = MagicMock(return_value=[TranscriptSegment(
        content="Test content",
        start_timestamp=0.0,
        end_timestamp=1.0,
        speaker="speaker1",
        confidence=0.9,
        segment_id=1,
        words=[["test", 0.0, 1.0]]
    )])
    
    # Mock overlapping connections
    processor.overlapping_connections = []
    
    # Create a list to store post calls
    post_calls = []
    
    # Create a function that returns a new post context manager for each call
    def create_post_cm(*args, **kwargs):
        mock_post = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"segments": [
            {
                "text": "Test content",
                "start": 0.0,
                "end": 1.0,
                "words": [["test", 0.0, 1.0]]
            }
        ]})
        mock_post.__aenter__.return_value = mock_response
        post_calls.append(mock_post)
        return mock_post
    
    # Mock session context managers
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = AsyncMock(post=create_post_cm)
    
    with patch('aiohttp.ClientSession', return_value=mock_session), \
         patch('app.services.audio.redis_models.Transcript.lpush'), \
         patch('app.services.transcription.matcher.TranscriptSegment.from_whisper_segment', return_value=TranscriptSegment(
             content="Test content",
             start_timestamp=0.0,
             end_timestamp=1.0,
             speaker="speaker1",
             confidence=0.9,
             segment_id=1,
             words=[["test", 0.0, 1.0]]
         )):
        await processor.transcribe()
        
        # Verify post context manager was entered
        assert len(post_calls) == 1
        assert post_calls[0].__aenter__.called
        
        # Verify counter was reset
        assert processor._failed_ingestions["test-meeting"] == 0 