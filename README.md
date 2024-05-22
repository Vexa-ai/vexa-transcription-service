
https://github.com/pyannote/pyannote-audio/issues/1563

```
torch==2.0.1
pyannote-audio==3.1.0
```

### ways to improve diarization 

- pass speaker embeddings to the main engine and build similarizy matrix of all the participants to find the redundunt speakers. Those might be that spoke a little and have embedding similar to one of the main vectors

- clean up overlapped speakers 

- check if start/end of diarization segments well align with transctiption and find out why not





# current todo

switch to stream api instread of redis



# docker compose -f /home/dima/0/0_stream/docker-compose.yml -p dev_dima_0 up -d;
# docker compose -f /home/dima/0/1_audio/docker-compose.yml -p dev_dima_1 up -d;
# docker compose -f /home/dima/0/2_engine/docker-compose.yml -p dev_dima_2 up -d;



uvicorn app.main:app --host 0.0.0.0 --port 8009 --reload

