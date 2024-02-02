from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.http.models import PointStruct
from uuid import uuid4
from pyannote.audio import Pipeline
import io
import pandas as pd
from qdrant_client import QdrantClient
from audio.redis import *
import asyncio
import torch

client = QdrantClient("qdrant")




def get_stored_knn(emb:list, client_id):
    search_result = client.search(
        collection_name=client_id, query_vector=emb, limit=1)
    if len(search_result)>0:
        search_result = search_result[0]
        return search_result.payload['speaker_id'], search_result.score
    else: return None,None

def create_collection_ifnotexists(client_id):
    if not client_id in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=client_id,
            vectors_config=VectorParams(size=256, distance=Distance.COSINE),
        )


def add_new_speaker_emb(emb:list,client_id,speaker_id=None):
    speaker_id = speaker_id if speaker_id else str(uuid4())

    operation_info = client.upsert(
        collection_name=client_id,
        wait=True,
        points=[PointStruct(id=str(uuid4()), vector=emb,payload={'speaker_id':speaker_id})]

    )

    return speaker_id



def process_speaker_emb(emb:list,client_id):
    speaker_id, score = get_stored_knn(emb, client_id)
    print(score)
    if speaker_id:
        if score > 0.95:
            pass
        elif score > 0.9:
            add_new_speaker_emb(emb,client_id,speaker_id=speaker_id)
        else:
            speaker_id = add_new_speaker_emb(emb,client_id)
    else:
        speaker_id = add_new_speaker_emb(emb,client_id)

    return str(speaker_id), score


def parse_segment(segment):
    return segment[0].start, segment[0].end,int(segment[-1].split('_')[1])

async def process(redis_client):
    # try:
    _,item = await redis_client.brpop('Audio2DiarizeQueue')
    audio_name,client_id = item.split(':')
    create_collection_ifnotexists(client_id)
    audio = Audio(audio_name,redis_client)
    #diarization = Diarisation(audio_name,redis_client)
    if await audio.get():
        print('here')
        output, embeddings = pipeline(io.BytesIO(audio.data), return_embeddings=True)
        if len(embeddings)==0: audio.delete()
    speakers =[process_speaker_emb(e,client_id)[0] for e in embeddings]
    segments = [i for i in output.itertracks(yield_label=True)]
    df = pd.DataFrame([parse_segment(s) for s in segments],columns = ['start','end','speaker'])
    df['speaker'] = df['speaker'].replace({i:s for i,s in enumerate(speakers)})
    diarization_data = df.to_dict('records')
    await Diarisation(audio_name,redis_client,diarization_data).save()
    print('done')
    # except Exception as e:
    #     print(e)
    # finally:
    await redis_client.lpush(f'DiarizeReady:{audio_name}', 'Done')


async def main():
    redis_client = await get_inner_redis()
    try:
        while True:
            await process(redis_client)
    except KeyboardInterrupt:
        pass 
    finally:
        redis_client.close()
      #  await redis_client.wait_closed()


if __name__ == '__main__':


    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token="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")
    pipeline.to(torch.device("cuda"))
                               
                               


    asyncio.run(main())
