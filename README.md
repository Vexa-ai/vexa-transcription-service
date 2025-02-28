# Real-Time Audio Transcription Service

A production-ready, scalable real-time audio transcription system designed for enterprise and SaaS applications. This service functions as the backbone for real-time transcription across various communication platforms, converting audio chunks into text with advanced speaker identification capabilities.

## Data Privacy & Security

### Private Deployment for Enterprises
One of the primary advantages of this system is its ability to be deployed entirely within an organization's private infrastructure. Unlike cloud-based transcription services:

- **Complete data sovereignty**: All audio data and transcriptions remain within your organization's boundaries
- **No external data sharing**: Sensitive meeting content never leaves your network
- **Compliance-friendly**: Helps meet regulatory requirements for data handling (GDPR, HIPAA, etc.)
- **Custom security policies**: Apply your organization's existing security protocols and access controls
- **Airgapped deployment options**: Can operate in environments with no internet access for maximum security


## Use Cases

### Enterprise Meeting Transcription
- Automatically transcribe all company meetings across Google Meet, Zoom, and Microsoft Teams
- Identify speakers correctly even in large meetings
- Store searchable transcripts with speaker attribution

### Customer Service and Call Centers
- Transcribe customer calls in real-time
- Provide agents with live transcription during calls
- Archive conversations with accurate speaker identification

### Educational Environments
- Transcribe lectures and classes conducted over video conferencing platforms
- Generate accessible content for students with hearing impairments
- Create searchable archives of educational content

### Content Creation
- Automatically transcribe podcasts and interviews
- Generate subtitles for video content
- Create text versions of audio content for multi-channel publishing

## Integration Examples

### Google Meet Integration
The system automatically extracts speaker identification data from Google Meet sessions, matching speakers to their transcribed content with high accuracy.

### Zoom Integration
Compatible with Zoom's audio streams, allowing for real-time transcription of Zoom meetings and webinars.

### Custom Client Integration
The API is designed to be easily integrated with custom clients, providing a simple interface for sending audio chunks and retrieving transcriptions. 



## Features

- **Multi-platform support**: Works seamlessly with Google Meet, Zoom, Microsoft Teams, Slack and other communication platforms
- **Automatic speaker identification**: Extracts speaker information directly from Google Meet and compatible platforms
- **Real-time processing**: Handles audio chunks sent every 3 seconds
- **Speaker mapping**: Optional speaker name mapping with 1-second update intervals
- **Low latency**: Provides transcriptions with only 5-10 second latency
- **Reliable storage**: Saves transcribed segments to Redis
- **Webhook integration**: Optional webhook calls to external APIs
- **Scalable architecture**: Built on containerized microservices for enterprise workloads
- **High accuracy**: Uses the optimized Whisper large-v3 model for transcription
- **Production-ready**: Designed for enterprise and SaaS deployment
- **Open-source**: Fully open-source implementation

## System Architecture

The system consists of several key components working together in a production-ready architecture:

### 1. StreamQueue API
- Acts as the entry point for audio streams from communication platforms
- Ensures reliable ingestion of audio chunks with guaranteed delivery
- Handles high-volume traffic from multiple concurrent sessions
- Provides robust error handling and recovery mechanisms

### 2. Audio Processing Service
- Processes incoming audio streams from various communication platforms
- Handles audio file storage and metadata management with optimized performance
- Calls the Whisper service for high-accuracy transcription
- Maps transcriptions with speaker information extracted from platforms like Google Meet
- Stores results in Redis with appropriate TTL settings
- Optionally forwards to downstream services via webhooks

### 3. Whisper Service
- Provides scalable, GPU-accelerated speech-to-text using faster-whisper
- Deployed using Ray Serve for efficient resource utilization
- Low-latency processing for real-time applications

### 4. Redis Storage
- Central storage for transcribed segments
- Enables fast retrieval and persistence
- Serves as a message broker between components

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with appropriate drivers (for Whisper Service)

## Quick Start

### 1. Clone the repositories

```bash
# Clone the audio processing service
git clone https://github.com/yourusername/audio.git

# Clone the whisper service
git clone https://github.com/yourusername/whisper_service.git
```

### 2. Set up environment variables

Copy the example environment files and configure them:

```bash
# For audio service
cd audio
cp .env.example .env

# For whisper service
cd ../whisper_service
cp .env.example .env
```

Edit the `.env` files to configure your setup. **Critical settings include**:

**For whisper_service/.env:**
```
WHISPER_API_TOKEN=your_secure_token  # Must match WHISPER_API_TOKEN in audio/.env
WHISPER_MODEL_SIZE=large-v3
WHISPER_DEVICE=cuda                  # Ensure this is set to 'cuda' for GPU acceleration
WHISPER_NUM_GPUS=0.5                 # Adjust based on your GPU resources
```

**For audio/.env:**
```
# Connection to Whisper Service
WHISPER_SERVICE_URL=http://host.docker.internal:8033  # Adjust if running on different hosts
WHISPER_API_TOKEN=your_secure_token                   # Must match token in whisper_service

# Webhook connection (if using)
ENGINE_API_URL=http://your-api-endpoint
ENGINE_API_TOKEN=your_webhook_token
```

### 3. Start the Whisper Service with GPU Access

Ensure your system has NVIDIA Docker support installed:

```bash
# Check NVIDIA Docker installation
nvidia-smi
docker run --gpus all nvidia/cuda:11.0-base nvidia-smi
```

Start the Whisper Service with GPU access:

```bash
cd whisper_service
docker-compose up -d
```

**Important:** Verify the service has GPU access by checking the logs:

```bash
docker-compose logs
```

You should see logs indicating the CUDA device is being used. If not, check your Docker GPU setup.

### 4. Start the Audio Service

Once the Whisper Service is running properly with GPU access:

```bash
cd ../audio
docker-compose up -d
```

Verify proper startup:

```bash
docker-compose logs
```

### 5. Testing Your Installation

To ensure everything is working properly:

```bash
# Test the Whisper Service directly
curl -X POST \
  "http://localhost:8033/" \
  -H "Authorization: Bearer your_whisper_api_token" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @sample_audio.webm

# Test the Audio Service
curl -X POST \
  "http://localhost:8000/api/audio/stream" \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @audio_chunk.webm
```

## Integration Guide

### Client Integration

To integrate your client application with this service:

1. **Audio Capture Implementation**:
   - Capture audio in chunks (typically 3-second segments)
   - Convert/save as webm format (preferred)
   - Implement a queue mechanism in case of network issues

2. **Send Audio Data**:
   ```javascript
   // Example JavaScript code for sending audio chunks
   async function sendAudioChunk(audioBlob, sessionId) {
     try {
       const response = await fetch('http://your-server:8000/api/audio/stream', {
         method: 'POST',
         headers: {
           'Authorization': 'Bearer your_api_token',
           'Content-Type': 'application/octet-stream',
           'X-Session-ID': sessionId
         },
         body: audioBlob
       });
       return response.ok;
     } catch (error) {
       console.error('Error sending audio chunk:', error);
       return false;
     }
   }
   ```

3. **Speaker Information (if available)**:
   ```javascript
   // Example for sending speaker information
   async function updateSpeaker(sessionId, speakerName) {
     try {
       const response = await fetch('http://your-server:8000/api/speaker', {
         method: 'POST',
         headers: {
           'Authorization': 'Bearer your_api_token',
           'Content-Type': 'application/json'
         },
         body: JSON.stringify({
           session_id: sessionId,
           speaker_name: speakerName
         })
       });
       return response.ok;
     } catch (error) {
       console.error('Error updating speaker:', error);
       return false;
     }
   }
   ```

### Receiving Transcriptions

There are two ways to receive transcriptions:

#### 1. Implement a Webhook Endpoint

Create an API endpoint in your application to receive transcription data:

```python
from fastapi import FastAPI, Depends, HTTPException, Security, Body
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI()

class TranscriptionSegment(BaseModel):
    content: str
    start_timestamp: str
    end_timestamp: str
    speaker: str = None
    words: List[Dict[str, Any]] = []

@app.post("/api/transcriptions/{session_id}")
async def receive_transcription(
    session_id: str, 
    segments: List[TranscriptionSegment] = Body(...)
):
    # Process incoming transcription segments
    # Store in your database, display to user, etc.
    return {"status": "success"}
```

Configure this endpoint URL in your audio service's `.env` file:
```
ENGINE_API_URL=http://your-api-endpoint/api/transcriptions
ENGINE_API_TOKEN=your_secure_token
```

#### 2. Access Data from Redis

If you prefer direct access to Redis:

```python
import redis
import json

# Connect to Redis
r = redis.Redis(
    host='your_redis_host',
    port=6379,
    password='your_redis_password'
)

# Retrieve transcriptions for a session
def get_transcriptions(session_id):
    # Get all transcription segments for the session
    key = f"segments_transcribe:{session_id}"
    raw_data = r.lrange(key, 0, -1)
    
    # Parse JSON data
    segments = []
    for item in raw_data:
        segment = json.loads(item)
        segments.append(segment)
    
    return segments
```


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Ray Serve](https://docs.ray.io/en/latest/serve/index.html)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Redis](https://redis.io/)

