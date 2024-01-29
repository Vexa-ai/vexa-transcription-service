### build pgvector 

https://github.com/pgvector/pgvector


```
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
docker build --build-arg PG_MAJOR=15 -t myuser/pgvector .```

`engine_execute('CREATE EXTENSION vector;')`

