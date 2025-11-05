# Starting Docker

## Docker Desktop Not Running

The Docker daemon needs to be running before you can use docker-compose.

### Start Docker Desktop

**macOS:**
1. Open Docker Desktop application
2. Wait for it to start (whale icon in menu bar)
3. Verify it's running: `docker ps` should work

**Or via command line:**
```bash
open -a Docker
```

### Verify Docker is Running

```bash
# Check Docker daemon
docker ps

# Should return empty list or running containers (not an error)
```

### Then Run docker-compose

Once Docker Desktop is running:

```bash
# Build and start
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Quick Test

```bash
# 1. Start Docker Desktop
open -a Docker

# 2. Wait 10-20 seconds for it to start

# 3. Verify
docker ps

# 4. Build and run
docker-compose up --build
```

## Troubleshooting

**"Cannot connect to Docker daemon"**
- Docker Desktop isn't running
- Start it: `open -a Docker`
- Wait for it to fully start (whale icon appears)

**"docker-compose: command not found"**
- Already installed via Homebrew
- May need to restart terminal or add to PATH
- Try: `brew link docker-compose`

**Plugin path warning**
- If `docker compose` (no hyphen) doesn't work, use `docker-compose` (with hyphen)
- The standalone version works fine

