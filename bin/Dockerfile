FROM python:3.12-slim

RUN apt-get update && apt-get install -y zip

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt -t /app/package
