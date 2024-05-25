# Vexa.audio

## Contents
- [Structure](#Structure)
- [Notes](#Notes)
  - [Ways to improve diarization](#ways-to-improve-diarization)
- [Envs](#Envs)
    - [prod](#prod)
    - [stage](#stage)
    - [dev-andrew](#dev-andrew)
    - [dev-dima](#dev-dima)
- [Run with Docker](#Run-with-Docker)
- [FastAPI](#FastAPI)

# Structure
- make `.env` based on `.env_example`
- `app/main.py` is the API

# Notes
https://github.com/pyannote/pyannote-audio/issues/1563

```
torch==2.0.1
pyannote-audio==3.1.0
```

## ways to improve diarization
- pass speaker embeddings to the main engine and build similarizy matrix of all the participants to find the redundunt speakers. Those might be that spoke a little and have embedding similar to one of the main vectors
- clean up overlapped speakers
- check if start/end of diarization segments well align with transctiption and find out why not

# Envs
## prod
*ToDo*

## stage
```dotenv
VOLUME_DATA_PATH=/home/andrew/volumes
CHECK_AND_PROCESS_CONNECTIONS_INTERVAL_SEC=10.0

SERVICE_VERSION=0.0.1_stage
SERVICE_NAME="Audio API"
SERVICE_API_HOST="0.0.0.0"
SERVICE_API_PORT=8002
SERVICE_TOKEN=stage_token

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_IMAGE_PORT=6381

STREAM_QUEUE_SERVICE_LIST_CONNECTIONS=http://host.docker.internal:8000/api/v1/connections/list
STREAM_QUEUE_SERVICE_GET_NEXT_CHUNKS=http://host.docker.internal:8000/api/v1/tools/get-next-chunks
STREAM_QUEUE_SERVICE_HEALTH=http://host.docker.internal:8000/api/v1/health
STREAM_QUEUE_SERVICE_HEALTH_CHECK=http://host.docker.internal:8000/api/v1/hc
STREAM_QUEUE_SERVICE_REQUEST_TIMEOUT=5
STREAM_QUEUE_SERVICE_AUTH_TOKEN=stage_token
```
## dev-andrew
```dotenv
VOLUME_DATA_PATH=/home/andrew/volumes
CHECK_AND_PROCESS_CONNECTIONS_INTERVAL_SEC=0.0

SERVICE_VERSION=0.0.1_dev_andrew
SERVICE_NAME="Audio API"
SERVICE_API_HOST="0.0.0.0"
SERVICE_API_PORT=8006
SERVICE_TOKEN=andrew_token

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_IMAGE_PORT=6381

STREAM_QUEUE_SERVICE_LIST_CONNECTIONS=http://host.docker.internal:8000/api/v1/connections/list
STREAM_QUEUE_SERVICE_GET_NEXT_CHUNKS=http://host.docker.internal:8000/api/v1/tools/get-next-chunks
STREAM_QUEUE_SERVICE_HEALTH=http://host.docker.internal:8000/api/v1/health
STREAM_QUEUE_SERVICE_HEALTH_CHECK=http://host.docker.internal:8000/api/v1/hc
STREAM_QUEUE_SERVICE_REQUEST_TIMEOUT=5
STREAM_QUEUE_SERVICE_AUTH_TOKEN=stage_token
```
## dev-dima
```dotenv
VOLUME_DATA_PATH=/home/dima/ssd/1_feature
CHECK_AND_PROCESS_CONNECTIONS_INTERVAL_SEC=5.0

SERVICE_VERSION=0.0.1_dev_dima
SERVICE_NAME="Audio API"
SERVICE_API_HOST="0.0.0.0"
SERVICE_API_PORT=8009
SERVICE_TOKEN=dima_token

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_IMAGE_PORT=6381

STREAM_QUEUE_SERVICE_LIST_CONNECTIONS=http://host.docker.internal:8000/api/v1/connections/list
STREAM_QUEUE_SERVICE_GET_NEXT_CHUNKS=http://host.docker.internal:8000/api/v1/tools/get-next-chunks
STREAM_QUEUE_SERVICE_HEALTH=http://host.docker.internal:8000/api/v1/health
STREAM_QUEUE_SERVICE_HEALTH_CHECK=http://host.docker.internal:8000/api/v1/hc
STREAM_QUEUE_SERVICE_REQUEST_TIMEOUT=5
STREAM_QUEUE_SERVICE_AUTH_TOKEN=stage_token
```
# Run with Docker
Build:
```bash
docker compose build
```

Run:

#TODO: fix paths @ANdrew
<!-- - (prod)
  ```bash
  docker compose -f /home/dima/1_feature/1_audio/docker-compose.yml -p prod_1 up -d
  ```

-  (stage)
  ```bash
  docker compose -f /home/dima/1_feature/1_audio/docker-compose.yml -p stage_1 up -d
  ```

-  (dev-andrew)
  ```bash
  docker compose -f /home/andrew/1_feature/1_audio/docker-compose.yml -p dev_andrew_1 up -d
  ``` -->

-  (dev-dima)
  ```bash
  docker compose -f /home/dima/0/1_audio/docker-compose.yml -p dev_dima_1 up -d
  ```

## FastAPI
### Running FastAPI project - console

-  (stage)
  ```shell
  uvicorn app.main:app --host 0.0.0.0 --port 8002
  ```

-  (dev-andrew)
  ```shell
  uvicorn app.main:app --host 0.0.0.0 --port 8006
  ```

-  (dev-dima)
  ```shell
  uvicorn app.main:app --host 0.0.0.0 --port 8009
  ```
