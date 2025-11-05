#!/usr/bin/env python3
"""
Interactive replay test script - runs through multiple test scenarios
"""
import os
import sys
import yaml
import subprocess
import time

def update_config(key_path, value):
    """Update a nested config value."""
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    keys = key_path.split('.')
    d = config
    for k in keys[:-1]:
        d = d[k]
    d[keys[-1]] = value

    with open('config.yaml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

def run_test(name, frames, speed=1.0, market_filter=None):
    """Run a single test scenario."""
    print(f"\n{'='*60}")
    print(f"🧪 {name}")
    print(f"{'='*60}")

    # Generate test data
    print(f"📝 Generating {frames} frames...")
    subprocess.run([
        sys.executable, 'scripts/generate_test_replay_data.py',
        'logs/ws_raw.jsonl', str(frames)
    ], check=True)

    # Update config
    update_config('replay.enabled', True)
    update_config('replay.speed', speed)
    if market_filter:
        update_config('replay.market_filter', market_filter)
    else:
        update_config('replay.market_filter', [])

    print(f"⚙️  Config: speed={speed}x, filter={market_filter or 'all markets'}")
    print(f"▶️  Running replay...")
    print()

    # Run replay
    result = subprocess.run(
        [sys.executable, '-m', 'core.main'],
        capture_output=True,
        text=True,
        env={**os.environ, 'PYTHONPATH': '.'}
    )

    # Extract summary
    lines = result.stdout.split('\n') + result.stderr.split('\n')
    summary_lines = [l for l in lines if 'REPLAY SUMMARY' in l or 'frames_processed' in l or
                     'frames_dropped' in l or 'speedup' in l or 'wall_duration' in l]

    for line in summary_lines[-10:]:
        if 'replay]' in line:
            print(line)

    time.sleep(1)

def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.makedirs('logs', exist_ok=True)

    print("🚀 Replay Mode Test Suite")
    print("=" * 60)

    # Test 1: Normal speed
    run_test("Test 1: Normal Speed (1.0x)", frames=8, speed=1.0)

    # Test 2: Fast speed
    run_test("Test 2: Fast Speed (2.0x)", frames=10, speed=2.0)

    # Test 3: Market filtering
    run_test("Test 3: Market Filter (market:1 only)", frames=8, speed=1.0, market_filter=["market:1"])

    # Test 4: Slow speed
    run_test("Test 4: Slow Speed (0.5x)", frames=6, speed=0.5)

    # Reset config
    print(f"\n{'='*60}")
    print("🔄 Resetting config to disabled...")
    update_config('replay.enabled', False)
    update_config('replay.speed', 1.0)
    update_config('replay.market_filter', [])

    print("\n✅ All tests complete!")
    print("\nTo test manually:")
    print("  1. python scripts/generate_test_replay_data.py logs/ws_raw.jsonl [frames]")
    print("  2. Edit config.yaml: replay.enabled: true")
    print("  3. python -m core.main")

if __name__ == '__main__':
    main()

