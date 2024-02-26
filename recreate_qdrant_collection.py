from qdrant_client import QdrantClient, models

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


print('done')