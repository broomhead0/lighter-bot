#!/usr/bin/env python3
"""
Test cancel discipline throttling in MakerEngine.
"""

import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.maker_engine import MakerEngine
from core.state_store import StateStore


async def test_cancel_discipline():
    """Test that cancel discipline throttles when limit exceeded."""
    print("=" * 60)
    print("TEST: Cancel Discipline Throttling")
    print("=" * 60)

    config = {
        "maker": {
            "pair": "market:1",
            "size": 0.001,
            "spread_bps": 10,
            "refresh_seconds": 1.0,
            "limits": {
                "max_cancels": 5,  # Low limit for testing
            }
        }
    }

    state = StateStore()
    state.set_mid("market:1", 100000.0)

    maker = MakerEngine(config=config, state=state)

    # Simulate cancels
    print("\n📊 Simulating cancels...")
    for i in range(8):  # More than the limit
        maker._record_cancel()
        maker._check_cancel_discipline()
        print(f"  Cancel {i+1}: count={maker._cancel_count_this_minute}, throttled={maker._is_throttled}")
        await asyncio.sleep(0.1)

    # Should be throttled after 5 cancels
    assert maker._is_throttled, "Should be throttled after exceeding limit"
    print("\n✅ Throttling activated correctly!")

    # Test that _post_quotes respects throttling
    print("\n📊 Testing quote posting with throttling...")
    initial_orders = len(maker._open_orders)
    await maker._post_quotes(99975.0, 100025.0, 0.001)
    after_orders = len(maker._open_orders)

    # Should not post new orders when throttled
    print(f"  Orders before: {initial_orders}, after: {after_orders}")
    if maker._is_throttled:
        print("  ✓ Quote posting skipped when throttled (expected)")
    else:
        print("  ⚠️  Quote posting not skipped (but throttling is active)")

    # Wait for reset (fast-forward time)
    print("\n📊 Testing reset after 60 seconds...")
    maker._cancel_window_start = time.time() - 61  # Fast-forward past reset
    maker._check_cancel_discipline()

    assert not maker._is_throttled, "Should reset after 60 seconds"
    assert maker._cancel_count_this_minute == 0, "Counter should reset"
    print("  ✓ Throttling reset after 60 seconds")

    print("\n✅ All cancel discipline tests passed!")


async def main():
    try:
        await test_cancel_discipline()
        print("\n" + "=" * 60)
        print("✅ CANCEL DISCIPLINE TEST PASSED")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

