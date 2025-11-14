#!/usr/bin/env python3
"""Query Lighter API for fill history or position PnL.

This script attempts to query the Lighter exchange API to get:
1. Full fill/order history since inception
2. Current position PnL (realized + unrealized)

The exchange position updates include realized_pnl which is the source of truth.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_loader import load_config
from modules.trading_client import SignerClient


def main():
    cfg = load_config()
    api_cfg = cfg.get("api", {})

    base_url = api_cfg.get("base_url", "http://127.0.0.1:8787")
    account_index = int(api_cfg.get("account_index", 366110))
    api_key = api_cfg.get("key", "")

    print(f"Connecting to Lighter API: {base_url}")
    print(f"Account: {account_index}")
    print()

    client = SignerClient(
        base_url=base_url,
        account_index=account_index,
        key=api_key,
    )

    # Check available methods
    print("Available SignerClient methods:")
    methods = [m for m in dir(client) if not m.startswith("_")]
    relevant = [
        m
        for m in methods
        if any(
            term in m.lower()
            for term in ["order", "fill", "trade", "history", "position", "pnl", "account"]
        )
    ]
    for m in sorted(relevant):
        print(f"  - {m}")

    print()
    print("Checking for order/fill history endpoints...")
    print("Note: The Lighter API might require specific endpoints.")
    print("Check API documentation or inspect client methods.")

    # Try to get position info (which includes realized_pnl)
    print()
    print("Attempting to query position/PnL info...")
    try:
        # This is a placeholder - actual method depends on API
        # The exchange position updates show realized_pnl in the account_all channel
        # We might need to query via REST API or WebSocket subscription
        
        # Check if there's a get_account or get_position method
        if hasattr(client, "get_account"):
            result = client.get_account()
            print(f"Account info: {json.dumps(result, indent=2)}")
        elif hasattr(client, "get_position"):
            result = client.get_position(market_id=2)  # SOL market
            print(f"Position info: {json.dumps(result, indent=2)}")
        else:
            print("No direct method found. Check API docs or use WebSocket subscription.")
            print()
            print("Alternative: Parse Railway logs for position updates:")
            print("  railway logs --service lighter-bot | grep 'realized_pnl'")
            print()
            print("The position updates contain:")
            print("  - realized_pnl: Total realized PnL since inception (this is what UI shows!)")
            print("  - unrealized_pnl: Current unrealized PnL")
            print("  - position_value: Current position value")
    except Exception as e:
        print(f"Error querying: {e}")


if __name__ == "__main__":
    main()

