# Docker Deployment Guide

## Prerequisites

- Docker Desktop (macOS/Windows) or Docker Engine (Linux)
- Docker Compose (included in Docker Desktop, or install separately)

See [DOCKER_SETUP.md](DOCKER_SETUP.md) if you need to install Docker.

## Quick Start

### Build and Run

```bash
# Build the image
docker build -t lighter-bot .

# Run the container
docker run -d \
  --name lighter-bot \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  -p 9100:9100 \
  -e WS_URL=wss://mainnet.zklighter.elliot.ai/stream/market_stats:all \
  lighter-bot
```

### Using Docker Compose

**If docker-compose is installed:**
```bash
# Start the service
docker compose up -d
# OR (if using standalone)
docker-compose up -d

# View logs
docker compose logs -f
# OR
docker-compose logs -f

# Stop the service
docker compose down
# OR
docker-compose down
```

**If docker-compose is NOT available:**
```bash
# Use the helper script
./run-docker.sh

# Or manually:
docker build -t lighter-bot .
docker run -d --name lighter-bot --rm \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  -p 9100:9100 \
  lighter-bot

# View logs
docker logs -f lighter-bot

# Stop
docker stop lighter-bot
```

**Install docker-compose (macOS):**
```bash
brew install docker-compose
```

## Configuration

### Environment Variables

Set via `-e` flags or in `docker-compose.yml`:

- `WS_URL` - WebSocket URL (default from config.yaml)
- `LOG_LEVEL` - Logging level (default: INFO)
- `LIGHTER_CONFIG` - Config file path (default: /app/config.yaml)
- `PYTHONPATH` - Python path (default: /app)

### Volumes

The compose file mounts:
- `./config.yaml` - Read-only config file
- `./logs` - Logs directory (persisted)
- `./data` - Data directory (persisted)

## Health Checks

The container includes health checks:

- **Endpoint:** `http://localhost:9100/health`
- **Interval:** 30 seconds
- **Timeout:** 10 seconds
- **Start period:** 40 seconds (allows time for startup)

### Check Health Status

```bash
# Via curl
curl http://localhost:9100/health

# Via docker
docker inspect lighter-bot --format='{{.State.Health.Status}}'
```

### Health Endpoint Response

```json
{
  "status": "healthy",
  "ws_age_seconds": 2.5,
  "quote_age_seconds": 1.2,
  "timestamp": 1234567890.12
}
```

Status codes:
- `200` - Healthy (recent heartbeats within 60s)
- `503` - Unhealthy (no recent heartbeats)

## Telemetry

### Enable Telemetry

In `config.yaml`:
```yaml
telemetry:
  enabled: true
  port: 9100
```

### Access Metrics

```bash
# Prometheus-style metrics
curl http://localhost:9100/metrics
```

## Development

### Build for Development

```bash
docker build -t lighter-bot:dev .
```

### Run with Overrides

```bash
docker run -it --rm \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -e LOG_LEVEL=DEBUG \
  lighter-bot:dev
```

### View Container Logs

```bash
# Docker
docker logs -f lighter-bot

# Docker Compose
docker compose logs -f
```

### Execute Commands in Container

```bash
docker exec -it lighter-bot bash
```

## Troubleshooting

### Container Won't Start

1. Check logs: `docker logs lighter-bot`
2. Verify config: `docker exec lighter-bot cat /app/config.yaml`
3. Check health: `curl http://localhost:9100/health`

### Health Check Failing

1. Ensure telemetry is enabled in config
2. Wait for startup period (40s)
3. Check if heartbeats are being generated
4. Verify port 9100 is accessible

### Permission Issues

If volumes have permission issues:
```bash
# Fix log directory permissions
chmod -R 777 logs
chmod -R 777 data
```

### Port Conflicts

If port 9100 is in use:
```yaml
# In docker-compose.yml, change:
ports:
  - "9101:9100"  # Map host 9101 to container 9100
```

## Production Deployment

### Recommendations

1. **Use secrets** for API keys (don't commit to config.yaml)
2. **Enable telemetry** for monitoring
3. **Set up log rotation** for logs volume
4. **Use restart policies**: `restart: unless-stopped`
5. **Monitor health checks** via orchestration (K8s, Docker Swarm)

### Example with Secrets

```yaml
# docker-compose.yml
services:
  lighter-bot:
    # ... other config ...
    secrets:
      - api_key
      - discord_webhook
    environment:
      - API_KEY_FILE=/run/secrets/api_key
      - DISCORD_WEBHOOK_FILE=/run/secrets/discord_webhook

secrets:
  api_key:
    file: ./secrets/api_key.txt
  discord_webhook:
    file: ./secrets/discord_webhook.txt
```

## Next Steps

- Set up monitoring (Prometheus + Grafana)
- Configure log aggregation
- Set up alerts for health check failures
- Implement graceful shutdown handling
- Add resource limits (CPU/memory)

