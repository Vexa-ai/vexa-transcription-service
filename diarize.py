import io

from sqlalchemy import select, update
from torch import cosine_similarity
from pyannote.audio import Pipeline
import pandas as pd
from audio.psql import *
from audio.redis import *
import asyncio
import torch

def get_stored_knn(emb, client_id):

    """get nearest neighbour and score"""

    q = session.scalars(select(SpeakerEmbs).filter(SpeakerEmbs.client_id==client_id).order_by(SpeakerEmbs.embedding.cosine_distance(emb)).limit(1)).first()
    if q:
        nearest = q.embedding
        nearest = torch.Tensor(q.embedding).unsqueeze(0)

        emb = torch.Tensor(emb).unsqueeze(0)
        return q.speaker_id, cosine_similarity(nearest, emb).item()
    else: None

def add_new_speaker(emb,client_id):
    new_speaker = Speakers(client_id=client_id)
    session.add(new_speaker)
    session.commit()
    speaker_emb_q = SpeakerEmbs(embedding=emb,client_id=client_id,speaker_id=new_speaker.id)
    session.add(speaker_emb_q)
    session.commit()
    return new_speaker.id



def process_speaker_emb(emb,client_id):
    knn = get_stored_knn(emb, client_id)
    if knn:
        speaker_id, score = get_stored_knn(emb, client_id)
        print(score)
        if update:
            if speaker_id:
                if score > 0.9:
                    identified_speaker = speaker_id
                elif score > 0.6:
                    identified_speaker = speaker_id
                    speaker_emb_q = SpeakerEmbs(embedding=emb,client_id=client_id,speaker_id=speaker_id)
                    session.add(speaker_emb_q)
                    session.commit()
                else:
                    speaker_id = add_new_speaker(emb,client_id)
            else:
                speaker_id = add_new_speaker(emb,client_id)
        else: pass

    else:
        speaker_id = add_new_speaker(emb,client_id)
        score = 0

    return str(speaker_id), score



def parse_segment(segment):
    return segment[0].start, segment[0].end,int(segment[-1].split('_')[1])

async def process(redis_client):
    _,item = await redis_client.brpop('Audio2DiarizeQueue')
    audio_name,client_id = item.split(':')
    print(client_id)
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
        await redis_client.publish(f'DiarizeReady', audio_name)
        print('done')


async def main():
    redis_client = await get_inner_redis()
    while True:
        await process(redis_client)


if __name__ == '__main__':

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token="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")
    pipeline.to(torch.device("cuda"))
                               
                               


    while True:
        asyncio.run(main())
