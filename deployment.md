# Google Cloud Run Deployment Plan for Audio Transcription Service

This document outlines the strategy for deploying the Audio Transcription Service on Google Cloud Run, taking advantage of serverless architecture with auto-scaling capabilities and pay-per-use pricing.

## Architecture Overview

The Audio Transcription Service consists of several components that will be deployed as separate Cloud Run services:

1. **StreamQueue API** - Handles incoming audio streams, ensures reliable ingestion
2. **Audio Processing Service** - Processes audio files, manages transcription workflow
3. **Redis** - Central storage for transcribed segments and coordination

Additionally, this service depends on:
- **Whisper Service** - GPU-accelerated speech-to-text service (assumed to be already deployed)

## Deployment Architecture

![Architecture Diagram](https://mermaid.ink/img/pako:eNp1kctOwzAQRX9l5FV3SH6ALbaglirYVKqQ2FRZmMmkdUnsYHsKFeq_YxxIoSLsZubOuY_R5ApZRnKRjOCGrYZ3O45TqRQCl2Y0SskBYPMoueHKIEzm1QDtUMUIy1sjx60d1yiD7UKQUBQwJINNXJBLpMF3GUF-Xqcw2-U5JF47PeCQRq_BR1CSeALb6rwDLpS5lx3UuC51WZXVsgj_5bIbrldhz3kHcbDufJXTi83f-FY6WvNCh591wVD2YHuHfPK8FkXbllzFt0-jnkbLbXW1O_Sm1A-L_Fzs-w4E92CMEUJ8FKCUVJAlKTnIpAVo0-2D36cQ-UyhM6zER6n0f7OdlWzrl8vFA2vosm-NgdqA_PsyEY9k-vU3K3QzvdL_XHW6X4xWa9AX47ru-j41mjjNvU5jnJoZOOkSnQzd0UdvOU3Z6vF-Jjq104NwaJj50Xj7DS33a4Y?type=png)

## Pre-deployment Steps

### 1. Prepare Environment Variables

Create a `.env.yaml` file for each service:

**streamqueue-env.yaml**:
```yaml
REDIS_HOST: <REDIS_HOST>
REDIS_PORT: 6379
REDIS_PASSWORD: <REDIS_PASSWORD>
API_HOST: 0.0.0.0
API_PORT: 8080
API_TOKEN: <API_TOKEN>
AUDIO_CHUNK_DURATION_SEC: 3
PYTHONPATH: /usr/src/app
```

**audio-env.yaml**:
```yaml
REDIS_HOST: <REDIS_HOST>
REDIS_PORT: 6379
REDIS_PASSWORD: <REDIS_PASSWORD>
AUDIO_CHUNK_DURATION_SEC: 3
SEGMENT_SIZE_SEC: 10
PROCESSING_THREADS: 4
CHECK_AND_PROCESS_CONNECTIONS_INTERVAL_SEC: 2.0
SPEAKER_DELAY_SEC: 1
WHISPER_SERVICE_URL: <WHISPER_SERVICE_URL>
WHISPER_API_TOKEN: <WHISPER_API_TOKEN>
RAW_AUDIO_PATH: /tmp/audio/raw
SEGMENTS_PATH: /tmp/audio/segments
TRANSCRIBER_STEP_SEC: 5
MAX_AUDIO_LENGTH_SEC: 60
ENGINE_API_URL: <ENGINE_API_URL>
ENGINE_API_TOKEN: <ENGINE_API_TOKEN>
PYTHONPATH: /usr/src/app
```

### 2. Set Up Serverless Redis

For a true serverless solution, we'll use Firebase Realtime Database or Firestore.

If you need Redis compatibility:
1. Create a small Memorystore for Redis instance
2. Set up a Serverless VPC Connector to access it

## Building Container Images

### 1. Modify Dockerfile

Create optimized Dockerfiles for Cloud Run:

**streamqueue/Dockerfile**:
```dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /usr/src/app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY streamqueue/ /usr/src/app/streamqueue/
COPY shared_lib/ /usr/src/app/shared_lib/

# Set Python path
ENV PYTHONPATH=/usr/src/app

# Start the server
ENTRYPOINT ["python", "-m", "streamqueue.main"]
```

**audio/Dockerfile**:
```dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /usr/src/app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg supervisor && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY app/ /usr/src/app/app/
COPY shared_lib/ /usr/src/app/shared_lib/

# Create necessary directories
RUN mkdir -p /tmp/audio/raw /tmp/audio/segments

# Set Python path
ENV PYTHONPATH=/usr/src/app

# Start supervisord
ENTRYPOINT ["supervisord", "-c", "/usr/src/app/app/supervisord.conf"]
```

### 2. Build and Push Images

```bash
# Build and push StreamQueue image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/streamqueue ./streamqueue

# Build and push Audio Processing image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/audio-processor .
```

## Deployment Steps

### 1. Deploy Serverless VPC Connector (if using Memorystore)

```bash
# Create a VPC connector
gcloud compute networks vpc-access connectors create redis-connector \
  --network default \
  --region us-central1 \
  --range 10.8.0.0/28
```

### 2. Deploy StreamQueue API

```bash
gcloud run deploy streamqueue \
  --image gcr.io/YOUR_PROJECT_ID/streamqueue \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 30 \
  --port 8080 \
  --env-vars-file streamqueue-env.yaml
```

If using VPC connector:
```bash
gcloud run services update streamqueue \
  --vpc-connector redis-connector
```

### 3. Deploy Audio Processing Service

```bash
gcloud run deploy audio-processor \
  --image gcr.io/YOUR_PROJECT_ID/audio-processor \
  --platform managed \
  --region us-central1 \
  --no-allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 20 \
  --timeout 3600 \
  --env-vars-file audio-env.yaml
```

If using VPC connector:
```bash
gcloud run services update audio-processor \
  --vpc-connector redis-connector
```

## Handling Persistent Storage

Since Cloud Run containers are ephemeral, we need to adjust the storage approach:

1. **Temporary Storage**: Use `/tmp` for processing files (included in the Dockerfile)
2. **Persistent Storage**: For longer retention, use Google Cloud Storage:

```bash
# Create a storage bucket for audio files
gsutil mb -l us-central1 gs://YOUR_PROJECT_ID-audio-files

# Add to environment variables
echo "GCS_BUCKET=gs://YOUR_PROJECT_ID-audio-files" >> audio-env.yaml
```

Modify code to use GCS for persistent storage if needed.

## Monitoring and Logging

Enable monitoring for your services:

```bash
# Set up Cloud Monitoring for Cloud Run services
gcloud services enable monitoring.googleapis.com

# View logs for the StreamQueue API
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=streamqueue"

# View logs for the Audio Processor
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=audio-processor"
```

## CI/CD Integration

Create a Cloud Build configuration file (`cloudbuild.yaml`):

```yaml
steps:
  # Build and push StreamQueue image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/${PROJECT_ID}/streamqueue', '-f', 'streamqueue/Dockerfile', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/${PROJECT_ID}/streamqueue']
  
  # Deploy StreamQueue to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'streamqueue'
      - '--image=gcr.io/${PROJECT_ID}/streamqueue'
      - '--platform=managed'
      - '--region=us-central1'
  
  # Build and push Audio Processor image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/${PROJECT_ID}/audio-processor', '-f', 'audio/Dockerfile', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/${PROJECT_ID}/audio-processor']
  
  # Deploy Audio Processor to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'audio-processor'
      - '--image=gcr.io/${PROJECT_ID}/audio-processor'
      - '--platform=managed'
      - '--region=us-central1'
```

## Service Communication

For the AudioProcessor to communicate with the Whisper Service, ensure:

1. The `WHISPER_SERVICE_URL` points to the Cloud Run URL of the deployed Whisper Service
2. Authentication is properly configured with `WHISPER_API_TOKEN`

## Cost Optimization

1. **Cold starts**: Both services are configured to scale to zero when not in use
2. **Resource allocation**: Memory and CPU settings are based on the service requirements
3. **Concurrency**: Default settings allow multiple requests per instance

## Considerations and Limitations

1. **WebSocket Support**: Cloud Run now supports WebSockets, but certain limitations apply
2. **Long-Running Processes**: The audio-processor service has a timeout of 3600 seconds (1 hour)
3. **Startup Time**: Supervisord may take a few seconds to start all processes

## Testing the Deployment

```bash
# Test the StreamQueue API
curl -X POST \
  "https://streamqueue-xxxxx-uc.a.run.app/api/audio/stream" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @sample_audio.webm
```

## Next Steps

1. **Custom Domain**: Configure a custom domain for your API
2. **Authentication**: Implement more robust authentication methods
3. **Scaling Parameters**: Fine-tune the min/max instances based on usage patterns 
4. **Monitoring**: Set up alerts for service health and performance 