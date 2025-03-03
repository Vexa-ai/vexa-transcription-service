import asyncio
import io
import json
import logging
import subprocess

from pydub import AudioSegment
from redis.asyncio.client import Redis
from shared_lib.redis.keys import AUDIO_BUFFER


class AudioFileCorruptedError(Exception):
    def __init__(self, message="AudioFile is corrupted"):
        super().__init__(message)


logger = logging.getLogger(__name__)


class AudioSlicer:
    def __init__(self, data=None, format="mp3"):
        self.format = format
        self.audio = AudioSegment.from_file(io.BytesIO(data), format=format) if data is not None else None

    @classmethod
    async def from_file(cls, file_path, format="mp3"):
        def read_file(file_path):
            with open(file_path, "rb") as file:
                return file.read()

        data = await asyncio.to_thread(read_file, file_path)
        return cls(data, format)
        
    @classmethod
    async def from_redis(cls, redis_client: Redis, connection_id: str, format="webm"):
        """Create an AudioSlicer from audio data stored in Redis.
        
        Args:
            redis_client: Redis client instance
            connection_id: Connection ID to retrieve audio for
            format: Audio format (default: webm)
            
        Returns:
            AudioSlicer instance with the audio data
            
        Raises:
            AudioFileCorruptedError: If the audio data is corrupted
        """
        redis_key = f"{AUDIO_BUFFER}:{connection_id}"
        hex_encoded_data = await redis_client.get(redis_key)
        
        if not hex_encoded_data:
            logger.error(f"No audio data found in Redis for connection {connection_id}")
            raise AudioFileCorruptedError(f"No audio data found in Redis for connection {connection_id}")
            
        try:
            # Convert hex encoded string back to binary data
            data = bytes.fromhex(hex_encoded_data)
            return cls(data, format)
        except ValueError as e:
            logger.error(f"Failed to decode hex data from Redis: {e}")
            raise AudioFileCorruptedError(f"Failed to decode hex data from Redis for connection {connection_id}") from e
        except Exception as e:
            logger.error(f"Failed to create AudioSlicer from Redis data: {e}")
            raise AudioFileCorruptedError(f"Audio data in Redis for connection {connection_id} is corrupted") from e

    @classmethod
    async def from_ffmpeg_slice(cls, path, start, duration, format="mp3"):
        def slice_and_get_data(path, start, duration):
            command = [
                "ffmpeg",
                # "-seekable",
                # "0",  # Add the -seekable 0 option
                "-ss",
                str(start),
                "-t",
                str(duration),
                "-i",
                path,
                "-f",
                format,
                "-acodec",
                "libmp3lame",
                "-rw_timeout",
                "5000000",  # Increase cache size timeout
                "-",
            ]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.stdout

        data = await asyncio.to_thread(slice_and_get_data, path, start, duration)

        try:
            return cls(data, format)

        except Exception as e:
            with open(path, "rb") as f:
                starting_bytes = f.read()
                if starting_bytes[:10] != b"\x1aE\xdf\xa3\x9fB\x86\x81\x01B":
                    logger.error(f"header is corrupted for audio file: {path}")
                    raise AudioFileCorruptedError(f"Audio File header {path} is corrupted") from e
            raise e
            
    @classmethod
    async def from_redis_slice(cls, redis_client: Redis, connection_id: str, start: float, duration: float, format="mp3"):
        """Create an AudioSlicer from a slice of audio data stored in Redis.
        
        This method retrieves audio data from Redis and slices it in memory using pydub,
        instead of using ffmpeg on a file.
        
        Args:
            redis_client: Redis client instance
            connection_id: Connection ID to retrieve audio for
            start: Start time in seconds
            duration: Duration in seconds
            format: Output format (default: mp3)
            
        Returns:
            AudioSlicer instance with the sliced audio data
        """
        # Get the full audio from Redis
        redis_key = f"{AUDIO_BUFFER}:{connection_id}"
        hex_encoded_data = await redis_client.get(redis_key)
        
        if not hex_encoded_data:
            logger.error(f"No audio data found in Redis for connection {connection_id}")
            raise AudioFileCorruptedError(f"No audio data found in Redis for connection {connection_id}")
        
        try:
            # Convert hex encoded string back to binary data
            data = bytes.fromhex(hex_encoded_data)
            
            # Load the full audio
            full_audio = AudioSegment.from_file(io.BytesIO(data), format="webm")
            
            # Calculate start and end in milliseconds
            start_ms = int(start * 1000)
            end_ms = int((start + duration) * 1000)
            
            # Slice the audio
            sliced_audio = full_audio[start_ms:end_ms]
            
            # Export to the requested format
            buffer = io.BytesIO()
            sliced_audio.export(buffer, format=format)
            
            # Create and return the AudioSlicer instance
            return cls(buffer.getvalue(), format)
            
        except Exception as e:
            logger.error(f"Failed to slice audio from Redis: {e}")
            logger.error(f"Data length: {len(data) if 'data' in locals() else 'N/A'}")
            
            # Check if we can identify a common WebM header issue
            if 'data' in locals() and len(data) > 10:
                header_bytes = data[:10].hex()
                expected_webm_header = "1a45dfa3".lower()  # First 4 bytes of a WebM file
                logger.error(f"Header bytes: {header_bytes}, Expected WebM header starts with: {expected_webm_header}")
                if not header_bytes.startswith(expected_webm_header):
                    logger.error("WebM header is corrupted or missing")
            
            raise AudioFileCorruptedError(f"Failed to slice audio for connection {connection_id}. {str(e)}") from e

    async def export2file(self, export_path, start=None, end=None):
        def export(segment, export_path):
            segment.export(export_path, format=self.format)

        segment = self.slice(start, end)
        await asyncio.to_thread(export, segment, export_path)

    async def export_data(self, start=None, end=None, format="mp3"):
        def export(segment, buffer):
            segment.export(buffer, format=format)
            return buffer.getvalue()

        segment = self.slice(start, end)
        buffer = io.BytesIO()
        return await asyncio.to_thread(export, segment, buffer)

    # slice remains synchronous as it's a simple in-memory operation
    def slice(self, start=None, end=None):

        if start is not None:
            start_millis = start * 1000
            end_millis = end * 1000
            audio = self.audio[start_millis:end_millis]
        else:
            logger.info(f"start: {start}")
            audio = self.audio

        return audio

    async def append(self, additional_data):
        def append_(additional_data):
            new_segment = AudioSegment.from_file(io.BytesIO(additional_data), format=self.format)
            self.audio += new_segment

        await asyncio.to_thread(append_, additional_data)


async def writestream2file(conn_id, redis_client):
    path = f"/audio/{conn_id}.webm"
    item = True
    while item:
        item = await redis_client.rpop(f"initialFeed_audio:{conn_id}")
        if item:
            chunk = bytes.fromhex(json.loads(item)["chunk"])
            # Open the file in append mode
            with open(path, "ab") as file:
                # Write data to the file
                file.write(chunk)
