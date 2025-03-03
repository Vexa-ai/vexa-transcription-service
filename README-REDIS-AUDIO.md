# Redis-Based Audio Processing

This document explains the Redis-based audio processing system implemented in the audio transcription service.

## Overview

The audio transcription system has been updated to store and process audio data in memory using Redis instead of writing to the file system. This approach offers several benefits:

1. **Improved Performance**: Reduces disk I/O operations
2. **Enhanced Scalability**: Better compatibility with containerized environments like Cloud Run
3. **Simplified Deployment**: Reduces dependency on persistent volumes
4. **Flexibility**: Can still fallback to file-based processing when needed
5. **Resilience**: Automatically restores audio buffers from Redis on restart

## How It Works

### Audio Data Flow

1. **Audio Chunk Collection**:
   - Audio chunks are sent to the service via the API
   - Chunks are initially stored in Redis using `AudioChunkDAL`

2. **In-Memory Processing**:
   - The `writestream2file` method in `Processor` class has been updated to:
     - Retrieve chunks from Redis
     - Append chunks to an in-memory buffer
     - Store the complete buffer in Redis with a backup TTL (24 hours)
     - Track the last activity timestamp for each connection
     - Return the same metadata as before for compatibility

3. **Audio Slicing**:
   - New methods in `AudioSlicer` allow creating and slicing audio segments directly from Redis data:
     - `from_redis`: Creates an AudioSlicer from complete audio data in Redis
     - `from_redis_slice`: Creates a sliced audio segment from Redis data

4. **Transcription Processing**:
   - The `read` method in the transcription `Processor` class tries to:
     - First retrieve and slice audio data from Redis
     - Fall back to file-based processing if Redis data is not available

5. **Activity-Based Flushing**:
   - The system tracks when each audio buffer was last updated
   - Connections that haven't been updated for a configurable time period (default: 60 seconds) are:
     - Flushed to disk for persistence
     - Removed from memory to free resources
     - Kept in Redis as a backup

6. **Resilient Initialization**:
   - On startup, the system loads existing audio buffers from Redis
   - This ensures data persistence across service restarts

### Key Components

1. **Redis Keys**:
   - `AUDIO_BUFFER`: Stores complete audio buffers (e.g., `audio_buffer:connection_id`)
   - `AUDIO_BUFFER_LAST_UPDATED`: Tracks when buffers were last updated (e.g., `audio_buffer_last_updated:connection_id`)

2. **Updated Classes**:
   - `Processor`: 
     - Added in-memory buffer management and Redis storage
     - Added activity tracking and automatic flushing of inactive connections
     - Added recovery of buffers on initialization
   - `AudioSlicer`: Added Redis-based methods for creating and slicing audio
   - `TranscriptionProcessor`: Updated to use Redis-based audio slicing

## Using the System

### Testing

A test script is provided at `app/tests/test_redis_audio.py` to demonstrate the Redis-based audio processing:

```bash
python -m app.tests.test_redis_audio
```

### Managing Redis Audio Buffers

A utility script is available to manage Redis audio buffers:

1. **List all audio buffers**:
   ```bash
   python -m app.scripts.flush_redis_buffers list
   ```

2. **Flush a specific buffer to disk**:
   ```bash
   python -m app.scripts.flush_redis_buffers flush <connection_id> [output_dir]
   ```

3. **Flush all buffers to disk**:
   ```bash
   python -m app.scripts.flush_redis_buffers flush-all [output_dir]
   ```

## Configuration

### Configurable Settings

1. **Inactivity Timeout**: The time (in seconds) of inactivity before a connection is flushed to disk. Default is 60 seconds:
   ```python
   processor = Processor()
   await processor.set_inactive_timeout(120)  # Set to 120 seconds
   ```

2. **Redis Backup TTL**: Audio buffers in Redis have a safety TTL of 24 hours. This can be adjusted in the `writestream2file` method in `processor.py`.

## Deployment Considerations

### Memory Usage

The in-memory approach uses more Redis memory, but connections are automatically flushed to disk after periods of inactivity, which helps manage memory use. Monitor Redis memory usage during high-traffic periods to ensure enough capacity.

### Persistence

Three layers of persistence are provided:

1. **In-Memory Buffers**: Fastest access for active connections
2. **Redis Storage**: Backup that survives service restarts
3. **Disk Storage**: Long-term persistence for inactive connections

Inactive connections are automatically flushed to disk after 60 seconds (configurable) of inactivity.

### Fallback Mechanism

The system includes multiple fallback mechanisms:

1. Redis data is restored on service restart
2. If Redis data is not available, it attempts to read from disk
3. On both Redis and disk failure, connections are gracefully removed

### Cleanup

Both automatic and manual cleanup options are available:

1. **Automatic**: Inactive connections are automatically flushed to disk and removed from memory
2. **Manual**: The utility script can be used to flush specific or all buffers as needed

## Troubleshooting

### Common Issues

1. **Redis Memory Issues**:
   - Symptom: Redis out of memory errors
   - Solution: 
     - Decrease the inactivity timeout to flush connections to disk more quickly
     - Increase Redis memory limit

2. **Missing Audio Data**:
   - Symptom: "No audio data found in Redis" errors
   - Solution: 
     - Check Redis connectivity
     - Verify that automatic flushing isn't removing buffers too aggressively

3. **Audio Format Issues**:
   - Symptom: "Failed to create AudioSlicer from Redis data" errors
   - Solution: Verify audio format compatibility and ensure audio chunks are valid

## Future Improvements

1. Implement a more sophisticated buffer management system with priority-based eviction
2. Add automatic backup of Redis buffers to Cloud Storage
3. Optimize memory usage by compressing audio data in Redis
4. Implement buffer sharing across multiple containers for enhanced scalability 