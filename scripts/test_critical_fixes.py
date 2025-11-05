#!/usr/bin/env python3
"""
Quick test script to verify critical fixes work:
1. SelfTradeGuard blocks invalid quotes
2. Cancel discipline throttles correctly
3. Inventory tracking works
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from core.state_store import StateStore
from modules.self_trade_guard import SelfTradeGuard
from modules.maker_engine import MakerEngine


def test_guard_blocking():
    """Test that SelfTradeGuard blocks invalid quotes."""
    print("=" * 60)
    print("TEST 1: SelfTradeGuard Blocking")
    print("=" * 60)
    
    state = StateStore()
    state.set_mid("market:1", 100000.0)
    state.set_inventory("market:1", Decimal("0"))
    
    guard_cfg = {
        "price_band_bps": 50,  # ±50 bps
        "crossed_book_protection": True,
        "max_position_units": 0.01,
        "max_inventory_notional": 1000,
    }
    guard = SelfTradeGuard(state=state, cfg=guard_cfg)
    
    mid = Decimal("100000")
    
    # Test 1: Valid quote should pass
    bid1 = Decimal("99975")  # 25 bps below mid
    ask1 = Decimal("100025")  # 25 bps above mid
    result1 = guard.is_allowed(mid, bid1, ask1, "market:1")
    print(f"✓ Valid quote (bid={bid1}, ask={ask1}): {'PASS' if result1 else 'FAIL'}")
    assert result1, "Valid quote should pass"
    
    # Test 2: Crossed book should fail
    bid2 = Decimal("100010")  # Above mid
    ask2 = Decimal("100000")  # Below mid (crossed!)
    result2 = guard.is_allowed(mid, bid2, ask2, "market:1")
    print(f"✓ Crossed book (bid={bid2}, ask={ask2}): {'BLOCKED' if not result2 else 'FAIL'}")
    assert not result2, "Crossed book should be blocked"
    
    # Test 3: Quote outside price band should fail
    bid3 = Decimal("99000")  # 100 bps below mid (too far)
    ask3 = Decimal("101000")  # 100 bps above mid
    result3 = guard.is_allowed(mid, bid3, ask3, "market:1")
    print(f"✓ Outside price band (bid={bid3}, ask={ask3}): {'BLOCKED' if not result3 else 'FAIL'}")
    assert not result3, "Quote outside price band should be blocked"
    
    # Test 4: Inventory breach should fail
    state.set_inventory("market:1", Decimal("0.02"))  # Exceeds max_position_units (0.01)
    result4 = guard.is_allowed(mid, bid1, ask1, "market:1")
    print(f"✓ Inventory breach (inv=0.02): {'BLOCKED' if not result4 else 'FAIL'}")
    assert not result4, "Inventory breach should be blocked"
    
    print("✅ All guard blocking tests passed!\n")


def test_inventory_tracking():
    """Test that StateStore inventory tracking works."""
    print("=" * 60)
    print("TEST 2: Inventory Tracking")
    print("=" * 60)
    
    state = StateStore()
    
    # Test per-market inventory
    state.set_inventory("market:1", Decimal("0.001"))
    state.set_inventory("market:2", Decimal("0.002"))
    
    inv1 = state.get_inventory("market:1")
    inv2 = state.get_inventory("market:2")
    
    print(f"✓ Market 1 inventory: {inv1} (expected: 0.001)")
    assert inv1 == Decimal("0.001"), f"Expected 0.001, got {inv1}"
    
    print(f"✓ Market 2 inventory: {inv2} (expected: 0.002)")
    assert inv2 == Decimal("0.002"), f"Expected 0.002, got {inv2}"
    
    # Test delta updates
    state.update_inventory("market:1", Decimal("0.001"))
    inv1_after = state.get_inventory("market:1")
    print(f"✓ After +0.001 delta: {inv1_after} (expected: 0.002)")
    assert inv1_after == Decimal("0.002"), f"Expected 0.002, got {inv1_after}"
    
    # Test all inventory
    all_inv = state.get_inventory()
    print(f"✓ All inventory: {all_inv}")
    assert "market:1" in all_inv and "market:2" in all_inv, "Should have both markets"
    
    print("✅ All inventory tracking tests passed!\n")


def test_order_tracking():
    """Test that StateStore order tracking works."""
    print("=" * 60)
    print("TEST 3: Order Tracking")
    print("=" * 60)
    
    state = StateStore()
    
    # Add orders
    order1 = {"side": "bid", "price": 100000.0, "size": 0.001, "market": "market:1"}
    order2 = {"side": "ask", "price": 100100.0, "size": 0.001, "market": "market:1"}
    
    state.add_order("order_1", order1)
    state.add_order("order_2", order2)
    
    # Get all orders
    all_orders = state.get_orders()
    print(f"✓ Total orders: {len(all_orders)} (expected: 2)")
    assert len(all_orders) == 2, "Should have 2 orders"
    
    # Get orders for specific market
    market_orders = state.get_orders("market:1")
    print(f"✓ Orders for market:1: {len(market_orders)} (expected: 2)")
    assert len(market_orders) == 2, "Should have 2 orders for market:1"
    
    # Remove order
    removed = state.remove_order("order_1")
    print(f"✓ Removed order_1: {removed['side']} (expected: bid)")
    assert removed["side"] == "bid", "Should return bid order"
    
    remaining = state.get_orders()
    print(f"✓ Remaining orders: {len(remaining)} (expected: 1)")
    assert len(remaining) == 1, "Should have 1 order left"
    
    print("✅ All order tracking tests passed!\n")


def test_guard_with_state_store():
    """Test that SelfTradeGuard works with StateStore methods."""
    print("=" * 60)
    print("TEST 4: Guard + StateStore Integration")
    print("=" * 60)
    
    state = StateStore()
    state.set_mid("market:1", 100000.0)
    state.set_inventory("market:1", Decimal("0.005"))  # Within limits
    
    guard_cfg = {
        "max_position_units": 0.01,
        "max_inventory_notional": 1000,
    }
    guard = SelfTradeGuard(state=state, cfg=guard_cfg)
    
    mid = Decimal("100000")
    bid = Decimal("99975")
    ask = Decimal("100025")
    
    # Should pass (inventory within limits)
    result1 = guard.is_allowed(mid, bid, ask, "market:1")
    print(f"✓ Valid quote with inventory: {'PASS' if result1 else 'FAIL'}")
    assert result1, "Should pass with valid inventory"
    
    # Exceed inventory limit
    state.set_inventory("market:1", Decimal("0.02"))  # Exceeds 0.01
    result2 = guard.is_allowed(mid, bid, ask, "market:1")
    print(f"✓ Quote with excessive inventory: {'BLOCKED' if not result2 else 'FAIL'}")
    assert not result2, "Should block when inventory exceeds limit"
    
    print("✅ Guard + StateStore integration tests passed!\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("CRITICAL FIXES VERIFICATION TEST")
    print("=" * 60 + "\n")
    
    try:
        test_inventory_tracking()
        test_order_tracking()
        test_guard_blocking()
        test_guard_with_state_store()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nCritical fixes verified:")
        print("  ✓ SelfTradeGuard blocks invalid quotes")
        print("  ✓ Inventory tracking works correctly")
        print("  ✓ Order tracking works correctly")
        print("  ✓ Guard integrates with StateStore")
        print("\nNote: Cancel discipline requires runtime testing (see test_chaos.py)")
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

