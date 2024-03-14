from qdrant_client import QdrantClient, models
from uuid import UUID
from qdrant_client.http.models import PointStruct
import asyncio
from audio.redis import get_inner_redis
from qdrant_client.http.models import PointStruct

client = QdrantClient("qdrant")

if len(client.get_collections().collections)>0:
    client.delete_collection(client.get_collections().collections[0].name)


client.create_collection(
    collection_name='main',
    vectors_config=models.VectorParams(size=256, distance=models.Distance.COSINE),
    hnsw_config=models.HnswConfigDiff(
        payload_m=16,
        m=0,
    ),
)
client.create_payload_index(
    collection_name='main',
    field_name="client_id",
    field_schema=models.PayloadSchemaType.KEYWORD,
)


print('recreated')



async def main():
    redis_client = await get_inner_redis()
    embs = await redis_client.get('embs_recovery')
    embs = eval(embs)

    points = [models.PointStruct(id=item['id'], 
                             vector=item['embedding'],
                             payload={'speaker_id': item['speaker_id'], 'client_id': item['client_id']})
          for item in embs]



    operation_info = client.upsert(
        collection_name="main",
        wait=True,
        points=points,
    )

    print(operation_info)
    print(client.get_collection('main').vectors_count)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()
