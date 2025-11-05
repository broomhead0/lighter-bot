#!/bin/bash
# Alternative Docker run script when docker-compose isn't available

set -e

cd "$(dirname "$0")"

echo "Building Docker image..."
docker build -t lighter-bot .

echo ""
echo "Starting container..."
docker run -d \
  --name lighter-bot \
  --rm \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/data:/app/data" \
  -p 9100:9100 \
  -e PYTHONPATH=/app \
  -e PYTHONUNBUFFERED=1 \
  -e LIGHTER_CONFIG=/app/config.yaml \
  -e LOG_LEVEL=INFO \
  lighter-bot

echo ""
echo "Container started! View logs with:"
echo "  docker logs -f lighter-bot"
echo ""
echo "Stop with:"
echo "  docker stop lighter-bot"

