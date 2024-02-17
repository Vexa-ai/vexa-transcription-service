
https://github.com/pyannote/pyannote-audio/issues/1563

```
torch==2.0.1
pyannote-audio==3.1.0
```

### ways to improve diarization 

- pass speaker embeddings to the main engine and build similarizy matrix of all the participants to find the redundunt speakers. Those might be that spoke a little and have embedding similar to one of the main vectors

- clean up oversapped speakers 

- check if start/end of diarization segments well align with transctiption and find out why not


