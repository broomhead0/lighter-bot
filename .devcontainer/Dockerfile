FROM mcr.microsoft.com/devcontainers/python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git make \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces/lighter-bot
COPY requirements.txt dev-requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt -r dev-requirements.txt

EXPOSE 9100
