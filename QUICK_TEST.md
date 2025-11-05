# Quick Testing Guide

## 🚀 Automated Test Suite

Run all tests automatically:
```bash
source .venv/bin/activate
export PYTHONPATH=.
python scripts/test_replay_interactive.py
```

This will test:
- ✅ Normal speed (1.0x)
- ✅ Fast speed (2.0x)
- ✅ Market filtering
- ✅ Slow speed (0.5x)

## 📝 Manual Testing

### Quick Test (10 seconds)
```bash
# 1. Generate test data
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 10

# 2. Enable replay in config.yaml
#    Set: replay.enabled: true

# 3. Run
source .venv/bin/activate
export PYTHONPATH=.
python -m core.main
```

### Test Different Speeds

**2x speed:**
```yaml
replay:
  enabled: true
  speed: 2.0
```

**0.5x speed:**
```yaml
replay:
  enabled: true
  speed: 0.5
```

### Test Market Filtering

**Only market:1:**
```yaml
replay:
  enabled: true
  market_filter: ["market:1"]
```

## ✅ What to Look For

**Success indicators:**
- `[main] REPLAY MODE enabled` message
- `[replay] starting replay from...` message
- `[router] mid updated market:X -> ...` messages
- `[replay] === REPLAY SUMMARY ===` at the end
- Bot exits cleanly when replay completes

**Summary metrics:**
- `frames_processed` should match generated frames
- `speedup` should be close to your speed setting
- `frames_dropped` should be 0 (unless filtering)

## 🔍 Debugging

**Check test data:**
```bash
head -1 logs/ws_raw.jsonl | python -m json.tool
```

**View replay logs:**
```bash
python -m core.main 2>&1 | grep -E "(replay|REPLAY|router)"
```

**Check config:**
```bash
grep -A 3 "replay:" config.yaml
```

## 📊 Test Results Summary

From the automated test run:
- ✅ Test 1 (1.0x): 8 frames in 7.01s → speedup 1.00x ✓
- ✅ Test 2 (2.0x): 10 frames in 4.51s → speedup 1.99x ✓
- ✅ Test 3 (filter): 8 frames filtered correctly ✓
- ✅ Test 4 (0.5x): 6 frames in 10.01s → speedup 0.50x ✓

All tests passed! 🎉

