import asyncio
import io
import json
import logging
import subprocess

from pydub import AudioSegment

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
    async def from_ffmpeg_slice(cls, path, start, duration, format="mp3"):
        def slice_and_get_data(path, start, duration):
            command = [
                "ffmpeg",
                "-seekable",
                "0",  # Add the -seekable 0 option
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
        return cls(data, format)

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
            logger.info(start)
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
