# Docker Guide

**Complete guide for running the lighter bot with Docker.**

---

## Prerequisites

### Install Docker

**macOS (Docker Desktop - Recommended):**
```bash
# Download from:
# https://www.docker.com/products/docker-desktop

# Or via Homebrew:
brew install --cask docker
```

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER  # Log out and back in
```

**Verify Installation:**
```bash
docker --version
docker compose version  # or docker-compose --version
```

### Start Docker Desktop

**macOS:**
```bash
open -a Docker
# Wait for whale icon in menu bar
```

**Verify Docker is Running:**
```bash
docker ps  # Should not error
```

---

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Build and start
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

**Note:** If `docker compose` doesn't work, try `docker-compose` (with hyphen).

### Using Docker Run

```bash
# Build image
docker build -t lighter-bot .

# Run container
docker run -d \
  --name lighter-bot \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  -p 9100:9100 \
  -e WS_URL=wss://mainnet.zklighter.elliot.ai/stream \
  lighter-bot

# View logs
docker logs -f lighter-bot

# Stop
docker stop lighter-bot
docker rm lighter-bot
```

---

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

---

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

---

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

---

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

---

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
chmod -R 777 logs
chmod -R 777 data
```

### Port Conflicts

If port 9100 is in use, change port mapping in `docker-compose.yml`:
```yaml
ports:
  - "9101:9100"  # Map host 9101 to container 9100
```

### "Cannot connect to Docker daemon"

- Docker Desktop isn't running
- Start it: `open -a Docker` (macOS)
- Wait for it to fully start

### "docker-compose: command not found"

**Use new syntax (no hyphen):**
```bash
docker compose up -d
```

**Or install standalone:**
```bash
brew install docker-compose  # macOS
sudo apt-get install docker-compose  # Linux
```

---

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

---

**Your bot is containerized and ready to deploy!** 🐳
