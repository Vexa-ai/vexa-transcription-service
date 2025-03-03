from app.redis_transcribe.connection import get_redis_client
from shared_lib.redis.dals.audio_chunk_dal import AudioChunkDAL

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional, Dict
import os
import io

from redis.asyncio.client import Redis

from app.services.audio.audio import AudioSlicer
from app.services.audio.redis_models import Connection, Meeting, Transcriber
from app.settings import settings

from shared_lib.redis.models import AudioChunkModel, SpeakerDataModel
from shared_lib.redis.keys import AUDIO_BUFFER, AUDIO_BUFFER_LAST_UPDATED

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        self.__running_tasks = set()
        self.__redis_client = None  # Will be initialized in setup
        self.__audio_buffers = {}  # In-memory audio buffers indexed by connection_id
        self.__buffer_last_updated = {}  # Timestamp of last update per connection
        self.__inactive_timeout = 60  # Seconds before an inactive connection is flushed to disk

    async def setup(self):
        """Initialize Redis client if not already initialized and load existing audio buffers."""
        if self.__redis_client is None:
            self.__redis_client = await get_redis_client(settings.redis_host, settings.redis_port, settings.redis_password)
            
        # Load existing audio buffers from Redis
        await self._load_audio_buffers_from_redis()
            
        return self.__redis_client
        
    async def _load_audio_buffers_from_redis(self):
        """Load existing audio buffers from Redis into memory cache."""
        pattern = f"{AUDIO_BUFFER}:*"
        buffer_count = 0
        
        logger.info("Loading existing audio buffers from Redis...")
        async for key in self.__redis_client.scan_iter(match=pattern):
            try:
                connection_id = key.split(':')[1]
                buffer_data = await self.__redis_client.get(key)
                
                if buffer_data:
                    # Create in-memory buffer
                    mem_buffer = io.BytesIO(buffer_data)
                    self.__audio_buffers[connection_id] = mem_buffer
                    
                    # Get last updated timestamp
                    timestamp_key = f"{AUDIO_BUFFER_LAST_UPDATED}:{connection_id}"
                    timestamp_str = await self.__redis_client.get(timestamp_key)
                    if timestamp_str:
                        try:
                            last_updated = datetime.fromisoformat(timestamp_str)
                            self.__buffer_last_updated[connection_id] = last_updated
                        except ValueError:
                            self.__buffer_last_updated[connection_id] = datetime.now(timezone.utc)
                    else:
                        self.__buffer_last_updated[connection_id] = datetime.now(timezone.utc)
                        
                    buffer_count += 1
            except Exception as e:
                logger.error(f"Error loading audio buffer from Redis: {e}")
        
        logger.info(f"Loaded {buffer_count} audio buffers from Redis")

    async def _get_new_connections(self):
        """Get new connections by scanning Redis for initialFeed_audio keys."""
        pattern = "initialFeed_audio:*"
        connections = []
        async for key in self.__redis_client.scan_iter(match=pattern):
            connection_id = key.split(':')[1]
            connections.append((connection_id, key))
        return connections

    async def process_connections(self):
        if not self.__redis_client:
            await self.setup()
        
        # Check for and flush inactive connections before processing
        await self.flush_inactive_connections()
        
        connections = await self._get_new_connections()
        for connection_id, key in connections:
            logger.info(f"Processing connection {connection_id}")
            await self._process_connection_task(connection_id)
            # Remove the key after processing
            await self.__redis_client.delete(key)

    async def _process_connection_task(
        self,
        connection_id,
        transcriber_step: int = None,
    ) -> None:
        # Use settings value if not provided
        if transcriber_step is None:
            transcriber_step = settings.transcriber_step_sec
        # Reuse the existing Redis client
        meeting_id, segment_start_user_timestamp, segment_end_user_timestamp, segment_start_server_timestamp, user_id = await self.writestream2file(connection_id)

        # If we didn't get valid data from writestream2file, skip processing
        if None in (meeting_id, segment_start_user_timestamp, segment_end_user_timestamp, segment_start_server_timestamp, user_id):
            logger.warning(f"Skipping processing for connection {connection_id} due to missing data")
            return

        current_time = datetime.now(timezone.utc) #TODO: consider using transcriber_last_updated_timestamp + step and rename to update_time

        connection = Connection(self.__redis_client, connection_id, user_id)
        await connection.update_timestamps(segment_start_user_timestamp, segment_end_user_timestamp)

        meeting = Meeting(self.__redis_client, meeting_id)

        await meeting.load_from_redis()
        await meeting.add_connection(connection.id)
        await meeting.set_start_timestamp(segment_start_user_timestamp)
        await meeting.set_start_server_timestamp(segment_start_server_timestamp)
        
        meeting.transcriber_last_updated_timestamp = (
            meeting.transcriber_last_updated_timestamp or segment_start_user_timestamp
        )

        time_since_last_update = (current_time - meeting.transcriber_last_updated_timestamp).seconds

        logger.info(f"Last transcriber update timestamp: {meeting.transcriber_last_updated_timestamp}")

        if time_since_last_update > transcriber_step:
            logger.info(f"Adding transcriber - time threshold exceeded ({time_since_last_update} > {transcriber_step} seconds)")
            transcriber = Transcriber(self.__redis_client)
            await transcriber.add_todo(meeting.meeting_id)
            await meeting.update_transcriber_timestamp(
                segment_start_user_timestamp, transcriber_last_updated_timestamp=current_time 
            )
        else:
            logger.info(f"Skipping transcriber addition - time threshold not met ({time_since_last_update} <= {transcriber_step} seconds)")

        await meeting.update_redis()

    async def writestream2file(self, connection_id) -> Tuple[Optional[str], Optional[datetime], Optional[datetime], Optional[datetime], Optional[str]]:
        """Process audio chunks for a connection, storing them in memory and Redis instead of writing to file.
        
        This method retrieves audio chunks from Redis and keeps them in memory and Redis instead
        of writing to disk. It maintains backward compatibility by returning the same metadata.
        
        Args:
            connection_id: The ID of the connection to process
            
        Returns:
            Tuple containing: meeting_id, first_user_timestamp, last_user_timestamp, 
            first_server_timestamp, and user_id
        """
        logger.info(f"Processing audio stream for connection {connection_id}")
        # Legacy path reference (not used for writing, but kept for reference)
        path = f"/data/audio/{connection_id}.webm"
        first_user_timestamp = None
        first_server_timestamp = None
        
        audio_chunk_dal = AudioChunkDAL(self.__redis_client)
        chunks = await audio_chunk_dal.pop_chunks(connection_id, limit=100)

        if not chunks:
            logger.info(f"No chunks found for connection {connection_id}")
            return None, None, None, None, None

        meeting_id = connection_id
        user_id = None
        
        # Initialize audio buffer for this connection if it doesn't exist
        if connection_id not in self.__audio_buffers:
            self.__audio_buffers[connection_id] = io.BytesIO()
            
        buffer = self.__audio_buffers[connection_id]
        
        for chunk_data in chunks:
            try:
                chunk_obj = AudioChunkModel(**chunk_data)
            except ValueError as e:
                logger.error(f"Invalid chunk data for connection {connection_id}: {e}")
                continue

            raw_chunk = bytes.fromhex(chunk_obj.chunk)
            first_user_timestamp = (
                datetime.fromisoformat(chunk_obj.user_timestamp.rstrip("Z")).astimezone(timezone.utc)
                - timedelta(seconds=chunk_obj.audio_chunk_duration_sec)
                if not first_user_timestamp
                else first_user_timestamp
            )
            
            first_server_timestamp = (
                datetime.fromisoformat(chunk_obj.server_timestamp.rstrip("Z")).astimezone(timezone.utc)
                - timedelta(seconds=chunk_obj.audio_chunk_duration_sec)
                if not first_server_timestamp
                else first_server_timestamp
            )
            
            # Append the chunk to our in-memory buffer
            buffer.write(raw_chunk)
            
            last_user_timestamp = datetime.fromisoformat(chunk_obj.user_timestamp.rstrip("Z")).astimezone(timezone.utc)
            
            meeting_id = chunk_obj.meeting_id or connection_id
            user_id = str(chunk_obj.user_id)
        
        # Update the last updated timestamp for this connection
        current_time = datetime.now(timezone.utc)
        self.__buffer_last_updated[connection_id] = current_time
        
        # Store the buffer in Redis and also write to disk for compatibility
        buffer_data = buffer.getvalue()
        if buffer_data:
            # Store the buffer in Redis with long expiration (e.g., 24 hours = 86400 seconds)
            # We'll use our own activity tracking for flushing
            redis_key = f"{AUDIO_BUFFER}:{connection_id}"
            timestamp_key = f"{AUDIO_BUFFER_LAST_UPDATED}:{connection_id}"
            
            # Hex encode the binary data before storing in Redis
            # This ensures binary audio data is properly stored and retrieved with Redis decode_responses=True
            hex_encoded_buffer = buffer_data.hex()
            await self.__redis_client.set(redis_key, hex_encoded_buffer, ex=86400)  # 24 hour TTL as safety
            await self.__redis_client.set(timestamp_key, current_time.isoformat(), ex=86400)
            
            # Also write to disk to maintain compatibility with previous implementation
            # This ensures proper WebM file structure for ffmpeg
            output_dir = "/data/audio"
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{connection_id}.webm")
            
            with open(file_path, "wb") as f:
                f.write(buffer_data)
            
            logger.info(f"Stored audio buffer in Redis and on disk for connection {connection_id} ({len(buffer_data)} bytes)")
        
        return meeting_id, first_user_timestamp, last_user_timestamp, first_server_timestamp, user_id
    
    async def get_audio_buffer(self, connection_id: str) -> bytes:
        """Get the audio buffer for a connection from memory or Redis.
        
        Args:
            connection_id: The connection ID
            
        Returns:
            The audio buffer as bytes or None if not found
        """
        # Try to get from memory first
        if connection_id in self.__audio_buffers:
            return self.__audio_buffers[connection_id].getvalue()
        
        # If not in memory, try to get from Redis
        redis_key = f"{AUDIO_BUFFER}:{connection_id}"
        hex_encoded_buffer = await self.__redis_client.get(redis_key)
        
        if hex_encoded_buffer:
            try:
                # Convert hex string back to binary
                # This works with decode_responses=True by converting hex string representation back to bytes
                buffer_data = bytes.fromhex(hex_encoded_buffer)
                return buffer_data
            except ValueError as e:
                logger.error(f"Error loading audio buffer from Redis: {e}")
                return None
        
        return None
    
    async def flush_inactive_connections(self):
        """Flush inactive connections to disk and remove them from memory."""
        current_time = datetime.now(timezone.utc)
        connections_to_flush = []
        
        # Identify inactive connections
        for connection_id, last_updated in self.__buffer_last_updated.items():
            time_since_update = (current_time - last_updated).total_seconds()
            if time_since_update > self.__inactive_timeout:
                connections_to_flush.append(connection_id)
        
        if not connections_to_flush:
            return
            
        logger.info(f"Flushing {len(connections_to_flush)} inactive connections to disk")
        
        # Flush each inactive connection
        for connection_id in connections_to_flush:
            await self.flush_connection_to_disk(connection_id)
    
    async def flush_connection_to_disk(self, connection_id: str) -> bool:
        """Flush a connection's audio buffer to disk and remove from memory.
        
        Args:
            connection_id: The connection ID to flush
            
        Returns:
            True if successful, False otherwise
        """
        if connection_id not in self.__audio_buffers:
            return False
            
        try:
            # Get the buffer data
            buffer_data = self.__audio_buffers[connection_id].getvalue()
            if not buffer_data:
                return False
                
            # Ensure directory exists
            output_dir = "/data/audio"
            os.makedirs(output_dir, exist_ok=True)
            
            # Write to disk
            file_path = os.path.join(output_dir, f"{connection_id}.webm")
            with open(file_path, "wb") as f:
                f.write(buffer_data)
                
            logger.info(f"Flushed buffer for connection {connection_id} to {file_path} ({len(buffer_data)} bytes)")
            
            # Remove from memory
            del self.__audio_buffers[connection_id]
            del self.__buffer_last_updated[connection_id]
            
            # We keep the Redis entries with their TTL to serve as a backup
            # but we could also delete them to save Redis memory:
            # redis_key = f"{AUDIO_BUFFER}:{connection_id}"
            # timestamp_key = f"{AUDIO_BUFFER_LAST_UPDATED}:{connection_id}"
            # await self.__redis_client.delete(redis_key, timestamp_key)
            
            return True
            
        except Exception as e:
            logger.error(f"Error flushing connection {connection_id} to disk: {e}")
            return False
    
    async def set_inactive_timeout(self, seconds: int):
        """Set the timeout for inactive connections before they're flushed to disk.
        
        Args:
            seconds: Number of seconds of inactivity before flushing
        """
        if seconds < 10:  # Set a reasonable minimum
            seconds = 10
            
        self.__inactive_timeout = seconds
        logger.info(f"Inactive connection timeout set to {seconds} seconds")