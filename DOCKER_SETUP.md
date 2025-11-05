# Docker Setup Instructions

## Installing Docker

### macOS

**Option 1: Docker Desktop (Recommended)**
```bash
# Download and install from:
# https://www.docker.com/products/docker-desktop

# Or via Homebrew:
brew install --cask docker
```

**Option 2: Install docker-compose separately**
```bash
# If you have Docker but not docker-compose
brew install docker-compose
```

### Linux (Ubuntu/Debian)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (optional, to avoid sudo)
sudo usermod -aG docker $USER

# Install docker-compose plugin (included in Docker Desktop)
# Or install standalone:
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

## Verify Installation

```bash
# Check Docker
docker --version

# Check Docker Compose (new syntax)
docker compose version

# Or check standalone (old syntax)
docker-compose --version
```

## Using Docker Compose

### New Syntax (Docker Desktop / Docker 20.10+)
```bash
docker compose up -d
docker compose logs -f
docker compose down
```

### Old Syntax (Standalone docker-compose)
```bash
docker-compose up -d
docker-compose logs -f
docker-compose down
```

## Troubleshooting

### "command not found: docker-compose"

**Solution 1:** Use new syntax (no hyphen)
```bash
docker compose up -d
```

**Solution 2:** Install standalone docker-compose
```bash
# macOS
brew install docker-compose

# Linux
sudo apt-get install docker-compose
```

### "command not found: docker"

Docker isn't installed. Install Docker Desktop or Docker Engine first.

### Permission Denied

```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER
# Then log out and back in

# Or use sudo (not recommended)
sudo docker compose up -d
```

## Quick Start After Installation

```bash
# Navigate to project
cd /Users/nico/cursour_lighter_bot/lighter-bot

# Build and run
docker compose up --build

# Or if using standalone:
docker-compose up --build
```

## Alternative: Run Without Docker

If you prefer not to use Docker, you can run locally:

```bash
# Setup virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
export PYTHONPATH=.
python -m core.main
```

