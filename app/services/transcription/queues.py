import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from redis.asyncio import Redis
from uuid import uuid4

logger = logging.getLogger(__name__)

@dataclass
class QueuedTranscript:
    meeting_id: str
    segment_id: int
    content: Dict[str, Any]
    retry_count: int = 0
    last_error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueuedTranscript':
        return cls(
            meeting_id=data['meeting_id'],
            segment_id=data['segment_id'],
            content=data['content'],
            retry_count=data.get('retry_count', 0),
            last_error=data.get('last_error')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'meeting_id': self.meeting_id,
            'segment_id': self.segment_id,
            'content': self.content,
            'retry_count': self.retry_count,
            'last_error': self.last_error
        }

class TranscriptQueueManager:
    """Manages the transcript ingestion queue system using reliable queue pattern."""
    
    INGESTION_QUEUE = "TranscriptIngestionQueue"
    PROCESSING_QUEUE = "TranscriptProcessingQueue"  # For in-progress items
    RETRY_QUEUE = "TranscriptRetryQueue"
    FAILED_QUEUE = "TranscriptFailedQueue"
    MAX_RETRIES = 5
    BASE_DELAY = 60  # Base delay in seconds
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def add_to_ingestion_queue(self, transcript: QueuedTranscript) -> bool:
        """Add a transcript to the ingestion queue."""
        try:
            await self.redis.lpush(
                self.INGESTION_QUEUE,
                json.dumps(transcript.to_dict())
            )
            logger.info(f"Added transcript {transcript.segment_id} from meeting {transcript.meeting_id} to ingestion queue")
            return True
        except Exception as e:
            logger.error(f"Failed to add transcript to ingestion queue: {str(e)}", exc_info=True)
            return False
    
    async def get_next_for_ingestion(self) -> Optional[QueuedTranscript]:
        """
        Get next transcript ready for ingestion using reliable queue pattern.
        Atomically moves item from ingestion queue to processing queue.
        """
        try:
            # First try the main ingestion queue using atomic RPOPLPUSH
            data = await self.redis.rpoplpush(
                self.INGESTION_QUEUE,
                self.PROCESSING_QUEUE
            )
            if data:
                return QueuedTranscript.from_dict(json.loads(data))
            
            # If no items in main queue, check retry queue for items ready to retry
            now = datetime.now(timezone.utc).timestamp()
            retry_items = await self.redis.zrangebyscore(
                self.RETRY_QUEUE,
                '-inf',  # Get all items with score less than now
                now,
                start=0,
                num=1
            )
            
            if retry_items:
                # First atomically move to temporary list
                temp_key = f"temp:{uuid4()}"
                try:
                    # Add to temp list
                    await self.redis.lpush(temp_key, retry_items[0])
                    # Remove from retry queue
                    await self.redis.zrem(self.RETRY_QUEUE, retry_items[0])
                    # Atomically move from temp to processing
                    data = await self.redis.rpoplpush(temp_key, self.PROCESSING_QUEUE)
                    if data:
                        return QueuedTranscript.from_dict(json.loads(data))
                finally:
                    # Cleanup temp key in case of any issues
                    await self.redis.delete(temp_key)
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting next transcript for ingestion: {str(e)}", exc_info=True)
            return None
    
    async def confirm_processed(self, transcript: QueuedTranscript) -> bool:
        """
        Confirm successful processing of a transcript.
        Removes it from the processing queue.
        """
        try:
            data = json.dumps(transcript.to_dict())
            removed = await self.redis.lrem(self.PROCESSING_QUEUE, 1, data)
            if removed:
                logger.info(
                    f"Confirmed processing of transcript {transcript.segment_id} "
                    f"from meeting {transcript.meeting_id}"
                )
            return bool(removed)
        except Exception as e:
            logger.error(f"Error confirming transcript processing: {str(e)}", exc_info=True)
            return False
    
    async def add_to_retry_queue(self, transcript: QueuedTranscript, error: str) -> bool:
        """
        Add a failed transcript to the retry queue with exponential backoff.
        Atomically moves from processing queue to retry queue via temporary list.
        """
        try:
            transcript.retry_count += 1
            transcript.last_error = error
            
            if transcript.retry_count >= self.MAX_RETRIES:
                return await self.add_to_failed_queue(transcript)
            
            # Calculate next retry time with exponential backoff
            delay = self.BASE_DELAY * (2 ** (transcript.retry_count - 1))
            next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
            data = json.dumps(transcript.to_dict())
            
            # Use temporary list for atomic move
            temp_key = f"temp:{uuid4()}"
            try:
                # First move from processing to temp list atomically
                await self.redis.rpoplpush(self.PROCESSING_QUEUE, temp_key)
                # Then add to retry queue with score
                await self.redis.zadd(self.RETRY_QUEUE, {data: next_retry.timestamp()})
                # Remove from temp list
                await self.redis.lrem(temp_key, 1, data)
                
                logger.info(
                    f"Added transcript {transcript.segment_id} from meeting {transcript.meeting_id} "
                    f"to retry queue. Attempt {transcript.retry_count}/{self.MAX_RETRIES}, "
                    f"next retry at {next_retry.isoformat()}"
                )
                return True
            finally:
                # Cleanup temp key
                await self.redis.delete(temp_key)
            
        except Exception as e:
            logger.error(f"Failed to add transcript to retry queue: {str(e)}", exc_info=True)
            return False
    
    async def add_to_failed_queue(self, transcript: QueuedTranscript) -> bool:
        """
        Add a transcript to the failed queue after exceeding max retries.
        Uses RPOPLPUSH for atomic move from processing to failed queue.
        """
        try:
            data = json.dumps(transcript.to_dict())
            
            # Atomically move from processing to failed queue
            await self.redis.rpoplpush(self.PROCESSING_QUEUE, self.FAILED_QUEUE)
            
            logger.error(
                f"Transcript {transcript.segment_id} from meeting {transcript.meeting_id} "
                f"failed after {transcript.retry_count} attempts. Last error: {transcript.last_error}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add transcript to failed queue: {str(e)}", exc_info=True)
            return False
    
    async def requeue_stuck_processing(self) -> int:
        """
        Requeue any stuck items in the processing queue back to the ingestion queue.
        This should be called on service startup to handle any items that were being
        processed when the service crashed.
        """
        try:
            count = 0
            while True:
                data = await self.redis.rpoplpush(
                    self.PROCESSING_QUEUE,
                    self.INGESTION_QUEUE
                )
                if not data:
                    break
                count += 1
            
            if count:
                logger.info(f"Requeued {count} stuck items from processing queue")
            return count
            
        except Exception as e:
            logger.error(f"Error requeuing stuck processing items: {str(e)}", exc_info=True)
            return 0
    
    async def get_queue_stats(self) -> Dict[str, int]:
        """Get current statistics about all queues."""
        try:
            ingestion_len = await self.redis.llen(self.INGESTION_QUEUE)
            processing_len = await self.redis.llen(self.PROCESSING_QUEUE)
            retry_len = await self.redis.zcard(self.RETRY_QUEUE)
            failed_len = await self.redis.llen(self.FAILED_QUEUE)
            
            return {
                'ingestion_queue': ingestion_len,
                'processing_queue': processing_len,
                'retry_queue': retry_len,
                'failed_queue': failed_len
            }
        except Exception as e:
            logger.error(f"Failed to get queue stats: {str(e)}", exc_info=True)
            return {
                'ingestion_queue': -1,
                'processing_queue': -1,
                'retry_queue': -1,
                'failed_queue': -1
            } 