FROM python:3.11-slim

RUN pip install --no-cache-dir numpy==2.2.6 pandas==2.2.3

USER 65534:65534
WORKDIR /tmp
