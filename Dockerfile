FROM python:3.12


# Set up app directory
WORKDIR /usr/src/app
ENV DEBIAN_FRONTEND=noninteractive

RUN python -m pip install --upgrade pip

# Install dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt
#RUN apt-get update && apt-get install -y ffmpeg

# Create necessary directories
RUN mkdir -p /usr/src/app/streamqueue /usr/src/app/app

# The actual application code will be mounted via volumes

