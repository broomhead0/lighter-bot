#!/bin/bash
# Quick test script for replay mode

set -e

cd "$(dirname "$0")/.."
export PYTHONPATH=.
source .venv/bin/activate

echo "🧪 Replay Mode Test Suite"
echo "=========================="
echo ""

# Test 1: Normal speed (1.0x)
echo "Test 1: Normal speed replay (1.0x)"
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 10
sed -i.bak 's/enabled: .*/enabled: true/' config.yaml
sed -i.bak 's/speed: .*/speed: 1.0/' config.yaml
echo "Running..."
python -m core.main 2>&1 | grep -E "(REPLAY|replay|frames_processed|speedup)" | tail -10
echo ""
sleep 2

# Test 2: Fast speed (2.0x)
echo "Test 2: Fast replay (2.0x)"
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 20
sed -i.bak 's/speed: .*/speed: 2.0/' config.yaml
echo "Running..."
python -m core.main 2>&1 | grep -E "(REPLAY|replay|frames_processed|speedup)" | tail -10
echo ""
sleep 2

# Test 3: Market filtering
echo "Test 3: Market filtering (market:1 only)"
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 15
sed -i.bak 's/speed: .*/speed: 1.0/' config.yaml
sed -i.bak 's/market_filter: .*/market_filter: ["market:1"]/' config.yaml
echo "Running..."
python -m core.main 2>&1 | grep -E "(REPLAY|replay|frames_processed|frames_dropped|market:1|market:55)" | tail -15
echo ""

# Reset config
echo "Resetting config..."
sed -i.bak 's/enabled: .*/enabled: false/' config.yaml
sed -i.bak 's/market_filter: .*/market_filter: []/' config.yaml
rm -f config.yaml.bak

echo "✅ All tests complete!"
echo ""
echo "To test manually:"
echo "  1. python scripts/generate_test_replay_data.py logs/ws_raw.jsonl [frames]"
echo "  2. Edit config.yaml: replay.enabled: true"
echo "  3. python -m core.main"

