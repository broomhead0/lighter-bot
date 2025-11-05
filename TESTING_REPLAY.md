# Testing Replay Mode (M8)

## Quick Start

### 1. Generate Test Data

```bash
export PYTHONPATH=.
source .venv/bin/activate

# Generate 50 frames (50 seconds of data)
python scripts/generate_test_replay_data.py

# Or generate more frames (200 frames = 200 seconds)
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 200
```

### 2. Enable Replay Mode

Edit `config.yaml` and set:
```yaml
replay:
  enabled: true
  path: "logs/ws_raw.jsonl"
  speed: 1.0
  market_filter: []
```

### 3. Run Replay

```bash
export PYTHONPATH=.
source .venv/bin/activate
python -m core.main
```

You should see:
- `[main] REPLAY MODE enabled: path=logs/ws_raw.jsonl speed=1.00x filter=None`
- `[replay] starting replay from logs/ws_raw.jsonl (speed=1.00x, filter=None)`
- `[router] mid updated market:1 -> ...` messages
- `[replay] === REPLAY SUMMARY ===` at the end

## Test Scenarios

### Test 1: Normal Replay (1.0x speed)

```bash
# 1. Generate test data
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 30

# 2. Edit config.yaml:
#    replay.enabled: true
#    replay.speed: 1.0

# 3. Run
python -m core.main
```

**Expected:**
- Replay completes in ~30 seconds
- Summary shows `speedup: ~1.0x`
- Frames processed = 30
- Router logs show mid updates for market:1 and market:55

### Test 2: Fast Replay (2.0x speed)

```bash
# 1. Generate test data
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 60

# 2. Edit config.yaml:
#    replay.enabled: true
#    replay.speed: 2.0

# 3. Run
python -m core.main
```

**Expected:**
- Replay completes in ~30 seconds (half the time)
- Summary shows `speedup: ~2.0x`
- Frames processed = 60

### Test 3: Market Filtering

```bash
# 1. Generate test data (includes market:1 and market:55)
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 50

# 2. Edit config.yaml:
#    replay.enabled: true
#    replay.speed: 1.0
#    replay.market_filter: ["market:1"]

# 3. Run
python -m core.main
```

**Expected:**
- Only market:1 frames are processed
- Router logs show only `market:1` updates
- Frames dropped > 0 (because market:55 frames are filtered out)

### Test 4: Missing File

```bash
# 1. Edit config.yaml:
#    replay.enabled: true
#    replay.path: "logs/nonexistent.jsonl"

# 2. Run
python -m core.main
```

**Expected:**
- Error log: `[replay] file not found: logs/nonexistent.jsonl`
- Bot exits gracefully

### Test 5: Slow Replay (0.5x speed)

```bash
# 1. Generate test data
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 20

# 2. Edit config.yaml:
#    replay.enabled: true
#    replay.speed: 0.5

# 3. Run
python -m core.main
```

**Expected:**
- Replay takes ~40 seconds (double the time)
- Summary shows `speedup: ~0.5x`

## Verify Replay is Working

Look for these log messages:

1. **Startup:**
   ```
   [main] REPLAY MODE enabled: path=logs/ws_raw.jsonl speed=1.00x filter=None
   [replay] starting replay from logs/ws_raw.jsonl (speed=1.00x, filter=None)
   ```

2. **During replay:**
   ```
   [router] got frame channel=market_stats:all type=update/market_stats
   [router] mid updated market:1 -> 107000.0
   [router] mid updated market:55 -> 0.366
   ```

3. **Completion:**
   ```
   [replay] === REPLAY SUMMARY ===
   [replay] frames_processed: 50
   [replay] frames_dropped: 0
   [replay] real_frames: 50
   [replay] synthetic_frames: 0
   [replay] wall_duration: 50.23s
   [replay] captured_timespan: 50.00s
   [replay] speedup: 0.99x
   [replay] ======================
   ```

## Testing with Real Captured Data

If you have real captured data from the listener:

1. Ensure your capture file matches the format:
   ```json
   {"ts": 1234567890.123, "raw": "{\"channel\":\"market_stats:all\",...}"}
   ```

2. Point replay to your file:
   ```yaml
   replay:
     enabled: true
     path: "logs/your_captured_data.jsonl"
     speed: 1.0
   ```

3. Run as normal

## Troubleshooting

**No frames processed:**
- Check file path is correct
- Verify file format (should be JSONL with `{"ts": ..., "raw": ...}`)
- Check logs for parsing errors

**Replay too fast/slow:**
- Adjust `replay.speed` in config.yaml
- Higher = faster, lower = slower

**No mid updates:**
- Check router logs for parsing errors
- Verify frame format matches expected structure
- Try without market_filter first

**Bot doesn't exit:**
- Replay should auto-stop when file ends
- Press Ctrl+C to stop manually
