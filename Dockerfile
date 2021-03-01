FROM python:3-slim
COPY ./requirements.txt /tmp
RUN pip install -U pip && pip install -r /tmp/requirements.txt
RUN apt update && apt install -y nano
RUN mkdir -p /doorbot
WORKDIR /doorbot
