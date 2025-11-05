#!/usr/bin/env python3
"""
Generate test replay data for M8 replay testing.
Creates a sample logs/ws_raw.jsonl file with realistic WS frames.
"""
import json
import os
import time
from datetime import datetime

def generate_test_data(output_path: str = "logs/ws_raw.jsonl", num_frames: int = 50):
    """Generate sample replay data."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    base_time = time.time() - 100  # Start 100 seconds ago
    base_price = 107000.0

    with open(output_path, "w") as f:
        for i in range(num_frames):
            # Simulate price movement
            drift = (i % 10) * 5.0 - 20.0  # oscillate
            price = base_price + drift

            # Create frame in the format captured by listener
            frame = {
                "channel": "market_stats:all",
                "type": "update/market_stats",
                "data": [
                    {
                        "market": "market:1",
                        "market_id": "market:1",
                        "mid": price,
                        "mark_price": price,
                        "index_price": price - 2.0,
                        "last_price": price + 2.0,
                    },
                    {
                        "market": "market:55",
                        "market_id": "market:55",
                        "mid": 0.366 + (i % 5) * 0.001,
                        "mark_price": 0.366 + (i % 5) * 0.001,
                    }
                ]
            }

            # Wrap in capture format: {"ts": timestamp, "raw": json_string}
            wrapped = {
                "ts": base_time + i * 1.0,  # 1 second per frame
                "raw": json.dumps(frame)
            }

            f.write(json.dumps(wrapped) + "\n")

    print(f"✅ Generated {num_frames} frames in {output_path}")
    print(f"   Timespan: {num_frames} seconds")
    print(f"   Markets: market:1, market:55")

if __name__ == "__main__":
    import sys
    output = sys.argv[1] if len(sys.argv) > 1 else "logs/ws_raw.jsonl"
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    generate_test_data(output, num)

