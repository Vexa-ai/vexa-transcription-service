### build pgvector 

https://github.com/pgvector/pgvector


```
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
docker build --build-arg PG_MAJOR=15 -t myuser/pgvector .```

`engine_execute('CREATE EXTENSION vector;')`



https://github.com/pyannote/pyannote-audio/issues/1563

```
torch==2.0.1
pyannote-audio==3.1.0
```

