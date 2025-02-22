import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.transcription.queues import TranscriptQueueManager, QueuedTranscript

@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    # Configure async Redis operations
    mock.lpush = AsyncMock(return_value=1)
    mock.rpop = AsyncMock(return_value=None)
    mock.rpoplpush = AsyncMock(return_value=None)
    mock.lrange = AsyncMock(return_value=[])
    mock.lrem = AsyncMock(return_value=1)
    mock.zadd = AsyncMock(return_value=1)
    mock.zrangebyscore = AsyncMock(return_value=[])
    mock.zrem = AsyncMock(return_value=1)
    mock.llen = AsyncMock(return_value=0)
    mock.zcard = AsyncMock(return_value=0)
    mock.delete = AsyncMock(return_value=1)
    return mock

@pytest.fixture
def queue_manager(mock_redis):
    return TranscriptQueueManager(mock_redis)

@pytest.fixture
def test_transcript():
    return QueuedTranscript(
        meeting_id="test-meeting",
        segment_id=1,
        content={
            "content": "Test content",
            "start_timestamp": "2024-03-13T15:32:42.170000+00:00",
            "end_timestamp": "2024-03-13T15:32:45.170000+00:00",
            "confidence": 0.95,
            "segment_id": 1,
            "words": [["test", 0.0, 1.0]],
            "speaker": "Speaker 1"
        }
    )

@pytest.mark.asyncio
async def test_add_to_ingestion_queue(queue_manager, test_transcript, mock_redis):
    # Test successful addition
    mock_redis.lpush.return_value = 1
    result = await queue_manager.add_to_ingestion_queue(test_transcript)
    assert result is True
    mock_redis.lpush.assert_called_once_with(
        queue_manager.INGESTION_QUEUE,
        json.dumps(test_transcript.to_dict())
    )
    
    # Test failure
    mock_redis.lpush.side_effect = Exception("Redis error")
    result = await queue_manager.add_to_ingestion_queue(test_transcript)
    assert result is False

@pytest.mark.asyncio
async def test_get_next_for_ingestion(queue_manager, test_transcript, mock_redis):
    # Test getting from main queue
    mock_redis.rpop.return_value = json.dumps(test_transcript.to_dict())
    result = await queue_manager.get_next_for_ingestion()
    assert result is not None
    assert result.meeting_id == test_transcript.meeting_id
    assert result.segment_id == test_transcript.segment_id
    
    # Test getting from retry queue when main queue is empty
    mock_redis.rpop.return_value = None
    mock_redis.zrangebyscore.return_value = [json.dumps(test_transcript.to_dict())]
    result = await queue_manager.get_next_for_ingestion()
    assert result is not None
    assert result.meeting_id == test_transcript.meeting_id
    mock_redis.zrem.assert_called_once()
    
    # Test when both queues are empty
    mock_redis.zrangebyscore.return_value = []
    result = await queue_manager.get_next_for_ingestion()
    assert result is None

@pytest.mark.asyncio
async def test_add_to_retry_queue(queue_manager, test_transcript, mock_redis):
    # Test adding to retry queue
    result = await queue_manager.add_to_retry_queue(test_transcript, "Test error")
    assert result is True
    assert test_transcript.retry_count == 1
    assert test_transcript.last_error == "Test error"
    mock_redis.zadd.assert_called_once()
    
    # Test moving to failed queue after max retries
    test_transcript.retry_count = queue_manager.MAX_RETRIES - 1
    result = await queue_manager.add_to_retry_queue(test_transcript, "Final error")
    assert result is True
    mock_redis.lpush.assert_called_once_with(
        queue_manager.FAILED_QUEUE,
        json.dumps(test_transcript.to_dict())
    )

@pytest.mark.asyncio
async def test_add_to_failed_queue(queue_manager, test_transcript, mock_redis):
    result = await queue_manager.add_to_failed_queue(test_transcript)
    assert result is True
    mock_redis.lpush.assert_called_once_with(
        queue_manager.FAILED_QUEUE,
        json.dumps(test_transcript.to_dict())
    )

@pytest.mark.asyncio
async def test_remove_from_main_queue(queue_manager, test_transcript, mock_redis):
    # Test removing single segment
    mock_redis.lrange.return_value = [json.dumps(test_transcript.to_dict())]
    result = await queue_manager.remove_from_main_queue(test_transcript.meeting_id, test_transcript.segment_id)
    assert result is True
    mock_redis.lrem.assert_called_once()
    
    # Test removing segment from list
    mock_redis.lrange.return_value = [json.dumps([test_transcript.to_dict()])]
    result = await queue_manager.remove_from_main_queue(test_transcript.meeting_id, test_transcript.segment_id)
    assert result is True
    mock_redis.lrem.assert_called()

@pytest.mark.asyncio
async def test_get_queue_stats(queue_manager, mock_redis):
    mock_redis.llen.side_effect = [5, 2]  # For ingestion and failed queues
    mock_redis.zcard.return_value = 3  # For retry queue
    
    stats = await queue_manager.get_queue_stats()
    assert stats == {
        'ingestion_queue': 5,
        'retry_queue': 3,
        'failed_queue': 2
    }
    
    # Test error handling
    mock_redis.llen.side_effect = Exception("Redis error")
    stats = await queue_manager.get_queue_stats()
    assert stats == {
        'ingestion_queue': -1,
        'retry_queue': -1,
        'failed_queue': -1
    }

@pytest.mark.asyncio
async def test_retry_queue_flow(queue_manager, test_transcript, mock_redis):
    """Test the complete flow of a transcript through the retry queue system"""
    # Initial ingestion
    mock_redis.lpush.return_value = 1
    await queue_manager.add_to_ingestion_queue(test_transcript)
    
    # Mock getting transcript from ingestion queue
    mock_redis.rpoplpush.return_value = json.dumps(test_transcript.to_dict())
    transcript = await queue_manager.get_next_for_ingestion()
    assert transcript is not None
    
    # Add to retry queue after first failure
    error_msg = "First failure"
    await queue_manager.add_to_retry_queue(transcript, error_msg)
    assert transcript.retry_count == 1
    assert transcript.last_error == error_msg
    
    # Verify retry delay calculation
    mock_redis.zadd.assert_called_once()
    call_args = mock_redis.zadd.call_args[0][1]
    retry_data = list(call_args.items())[0]
    retry_time = retry_data[1]
    expected_delay = queue_manager.BASE_DELAY * (2 ** 0)  # First retry
    assert abs(retry_time - (datetime.now(timezone.utc) + timedelta(seconds=expected_delay)).timestamp()) < 1

@pytest.mark.asyncio
async def test_retry_exponential_backoff(queue_manager, test_transcript, mock_redis):
    """Test exponential backoff timing for multiple retries"""
    now = datetime.now(timezone.utc)
    
    # Try multiple retries and check backoff timing
    for retry in range(3):
        await queue_manager.add_to_retry_queue(test_transcript, f"Failure {retry}")
        
        call_args = mock_redis.zadd.call_args[0][1]
        retry_data = list(call_args.items())[0]
        retry_time = retry_data[1]
        
        expected_delay = queue_manager.BASE_DELAY * (2 ** retry)
        expected_time = now + timedelta(seconds=expected_delay)
        assert abs(retry_time - expected_time.timestamp()) < 1
        
        mock_redis.zadd.reset_mock()

@pytest.mark.asyncio
async def test_retry_to_failed_queue(queue_manager, test_transcript, mock_redis):
    """Test transition from retry to failed queue after max retries"""
    # Set retry count to one less than max
    test_transcript.retry_count = queue_manager.MAX_RETRIES - 1
    
    # Next retry should move to failed queue
    await queue_manager.add_to_retry_queue(test_transcript, "Final failure")
    
    # Verify moved to failed queue
    mock_redis.lpush.assert_called_once_with(
        queue_manager.FAILED_QUEUE,
        json.dumps(test_transcript.to_dict())
    )
    
    # Verify not added to retry queue
    mock_redis.zadd.assert_not_called()

@pytest.mark.asyncio
async def test_get_next_from_retry_queue(queue_manager, test_transcript, mock_redis):
    """Test retrieving ready items from retry queue"""
    now = datetime.now(timezone.utc).timestamp()
    
    # Mock retry queue with items at different times
    ready_item = json.dumps(test_transcript.to_dict())
    future_item = json.dumps(test_transcript.to_dict())
    
    mock_redis.zrangebyscore.return_value = [ready_item]
    mock_redis.rpoplpush.side_effect = [None, ready_item]  # First from main queue (empty), then from temp
    
    # Get next item
    result = await queue_manager.get_next_for_ingestion()
    assert result is not None
    assert result.meeting_id == test_transcript.meeting_id
    
    # Verify correct Redis calls
    mock_redis.zrangebyscore.assert_called_with(
        queue_manager.RETRY_QUEUE,
        '-inf',
        now,
        start=0,
        num=1
    )
    mock_redis.zrem.assert_called_once_with(queue_manager.RETRY_QUEUE, ready_item)

@pytest.mark.asyncio
async def test_retry_queue_atomic_operations(queue_manager, test_transcript, mock_redis):
    """Test atomic operations in retry queue processing"""
    # Mock Redis errors during atomic operations
    mock_redis.rpoplpush.side_effect = Exception("Redis error")
    
    # Attempt to add to retry queue
    result = await queue_manager.add_to_retry_queue(test_transcript, "Test error")
    assert result is False
    
    # Verify temp key cleanup
    mock_redis.delete.assert_called()  # Should clean up temp key even on failure

@pytest.mark.asyncio
async def test_requeue_stuck_processing(queue_manager, test_transcript, mock_redis):
    """Test requeuing stuck items from processing queue"""
    # Mock three stuck items
    stuck_items = [json.dumps(test_transcript.to_dict()) for _ in range(3)]
    mock_redis.rpoplpush.side_effect = stuck_items + [None]  # Return 3 items then None
    
    count = await queue_manager.requeue_stuck_processing()
    assert count == 3
    
    # Verify each item was moved back to ingestion queue
    assert mock_redis.rpoplpush.call_count == 4  # 3 items + 1 final check
    for call in mock_redis.rpoplpush.call_args_list[:3]:
        assert call[0] == (queue_manager.PROCESSING_QUEUE, queue_manager.INGESTION_QUEUE)

@pytest.mark.asyncio
async def test_retry_queue_concurrent_safety(queue_manager, test_transcript, mock_redis):
    """Test concurrent safety mechanisms in retry queue operations"""
    # Simulate concurrent access scenarios
    mock_redis.watch.side_effect = Exception("Redis watch error")
    
    # Attempt retry queue operation
    result = await queue_manager.add_to_retry_queue(test_transcript, "Test error")
    assert result is False
    
    # Verify proper cleanup
    mock_redis.delete.assert_called()
    mock_redis.unwatch.assert_not_called()  # Should not unwatch if watch failed 