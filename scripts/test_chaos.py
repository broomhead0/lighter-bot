#!/usr/bin/env python3
"""
Test script for chaos injector - demonstrates different chaos scenarios
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
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value

    with open('config.yaml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

def run_test(name, chaos_config, frames=10):
    """Run a chaos test scenario."""
    print(f"\n{'='*60}")
    print(f"🧪 {name}")
    print(f"{'='*60}")

    # Generate test data
    print(f"📝 Generating {frames} frames...")
    subprocess.run([
        sys.executable, 'scripts/generate_test_replay_data.py',
        'logs/ws_raw.jsonl', str(frames)
    ], check=True)

    # Enable replay and chaos
    update_config('replay.enabled', True)
    update_config('replay.speed', 1.0)

    # Apply chaos config
    for key, value in chaos_config.items():
        update_config(f'chaos.{key}', value)

    print(f"⚙️  Chaos config: {chaos_config}")
    print(f"▶️  Running with chaos...")
    print()

    # Run
    result = subprocess.run(
        [sys.executable, '-m', 'core.main'],
        capture_output=True,
        text=True,
        env={**os.environ, 'PYTHONPATH': '.'}
    )

    # Extract chaos-related logs
    lines = result.stdout.split('\n') + result.stderr.split('\n')
    chaos_lines = [l for l in lines if 'chaos' in l.lower() or 'CHAOS' in l]

    for line in chaos_lines[:20]:  # Show first 20 chaos logs
        if line.strip():
            print(line)

    time.sleep(1)

def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.makedirs('logs', exist_ok=True)

    print("🚀 Chaos Injector Test Suite")
    print("=" * 60)

    # Test 1: Latency injection
    run_test(
        "Test 1: Latency Spikes",
        {
            'enabled': True,
            'latency.enabled': True,
            'latency.probability': 0.3,  # Higher prob for testing
            'latency.min_ms': 50.0,
            'latency.max_ms': 200.0,
        },
        frames=15
    )

    # Test 2: Quote width spikes
    run_test(
        "Test 2: Quote-Width Spikes",
        {
            'enabled': True,
            'quote_width.enabled': True,
            'quote_width.probability': 0.2,  # Higher prob for testing
            'quote_width.min_bps': 30.0,
            'quote_width.max_bps': 80.0,
        },
        frames=12
    )

    # Test 3: Cancel rate testing
    run_test(
        "Test 3: Cancel-Rate Testing",
        {
            'enabled': True,
            'cancel_rate.enabled': True,
            'cancel_rate.force_cancels_per_min': 30,
        },
        frames=10
    )

    # Reset config
    print(f"\n{'='*60}")
    print("🔄 Resetting config...")
    update_config('replay.enabled', False)
    update_config('chaos.enabled', False)
    update_config('chaos.latency.enabled', False)
    update_config('chaos.quote_width.enabled', False)
    update_config('chaos.cancel_rate.enabled', False)

    print("\n✅ All chaos tests complete!")
    print("\nChaos injector is working. Check logs above for chaos injections.")

if __name__ == '__main__':
    main()

