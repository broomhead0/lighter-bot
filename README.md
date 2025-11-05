# Lighter.xyz Points Bot

Automated Lighter.xyz Points Bot to maximize points per dollar per day with ~$1k capital.

## Features

- **Real-time market data** via WebSocket
- **Post-only maker quotes** on 2-3 markets
- **Adaptive spreads** with volatility awareness
- **Self-trade guard** and inventory caps
- **Cancel discipline** enforcement
- **Telemetry & alerts** (Prometheus-style metrics, Discord)
- **Replay mode** for testing (M8)
- **Chaos injector** for resilience testing (M8)
- **Docker support** with health checks (M8)

## Quick Start

### Local Development

```bash
# Setup
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
export PYTHONPATH=.
python -m core.main
```

### Docker

```bash
# Build
docker build -t lighter-bot .

# Run
docker compose up -d

# View logs
docker compose logs -f
```
```

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

## Configuration

Edit `config.yaml`:

```yaml
maker:
  pair: "market:1"
  spread_bps: 10
  size: 0.001
  post_only: true

optimizer:
  enabled: true
  scan_interval_s: 30
  top_n: 3

telemetry:
  enabled: true
  port: 9100
```

## Testing

### Replay Mode

```bash
# Generate test data
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 50

# Enable replay in config.yaml
# replay.enabled: true

# Run
python -m core.main
```

### Chaos Testing

```bash
# Run chaos tests
python scripts/test_chaos.py
```

See [TESTING_REPLAY.md](TESTING_REPLAY.md) and [CHAOS_TESTING.md](CHAOS_TESTING.md) for details.

## Health Checks

When telemetry is enabled, health endpoint is available:

```bash
curl http://localhost:9100/health
```

Returns JSON with status and heartbeat ages.

## Project Structure

```
.
├── core/              # Core orchestration
│   ├── main.py       # Main entry point
│   ├── state_store.py # State management
│   └── message_router.py # WS frame routing
├── modules/           # Feature modules
│   ├── maker_engine.py
│   ├── optimizer.py
│   ├── telemetry.py
│   └── chaos_injector.py
├── scripts/           # Utilities
│   ├── replay_sim.py
│   └── test_chaos.py
└── config.yaml        # Configuration
```

## Milestones

- **M0-M7**: Core functionality complete
- **M8**: Production hardening (replay, chaos, Docker)

## License

[Your License Here]

