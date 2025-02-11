FROM python:3.12

WORKDIR /usr/src/app
ENV DEBIAN_FRONTEND=noninteractive

RUN python -m pip install --upgrade pip

COPY  requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y ffmpeg