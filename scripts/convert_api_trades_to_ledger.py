#!/usr/bin/env python3
"""
Convert API trades (from query_api_history_v2.py) to MetricsLedger format.

API trades have a different format than what MetricsLedger expects.
This script converts them to the FillRecord format that export_pnl_windows.py needs.
"""
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

def convert_trade_to_fill_record(trade: Dict[str, Any], account_index: int) -> Dict[str, Any]:
    """Convert API trade format to FillRecord format."""
    # Determine our role
    ask_account = trade.get("ask_account_id") or trade.get("ask_account")
    bid_account = trade.get("bid_account_id") or trade.get("bid_account")
    is_maker_ask = trade.get("is_maker_ask", False)
    
    # Determine if we're maker or taker
    role = "unknown"
    if ask_account == account_index and is_maker_ask:
        role = "maker"
    elif bid_account == account_index and not is_maker_ask:
        role = "maker"
    elif ask_account == account_index or bid_account == account_index:
        role = "taker"
    
    # Determine side and base_delta
    if ask_account == account_index:
        # We're selling (ask side)
        side = "ask"
        base_delta = -Decimal(str(trade.get("size", "0")))
    elif bid_account == account_index:
        # We're buying (bid side)
        side = "bid"
        base_delta = Decimal(str(trade.get("size", "0")))
    else:
        # Not our trade
        return None
    
    # Get price and calculate notional
    price = Decimal(str(trade.get("price", "0")))
    size = Decimal(str(trade.get("size", "0")))
    notional = price * size
    
    # Get fees
    maker_fee = Decimal(str(trade.get("maker_fee", "0"))) / Decimal("10000")  # Convert from bps
    taker_fee = Decimal(str(trade.get("taker_fee", "0"))) / Decimal("10000")
    
    if role == "maker":
        fee_paid = notional * maker_fee
    else:
        fee_paid = notional * taker_fee
    
    # Calculate quote_delta
    if side == "ask":
        # Selling: we receive quote
        quote_delta = notional - fee_paid
    else:
        # Buying: we pay quote
        quote_delta = -(notional + fee_paid)
    
    # Get timestamp (convert from milliseconds to seconds)
    timestamp_ms = trade.get("timestamp") or trade.get("ts") or 0
    timestamp = float(timestamp_ms) / 1000.0 if timestamp_ms > 1e10 else float(timestamp_ms)
    
    # Get market
    market_id = trade.get("market_id")
    if isinstance(market_id, int):
        market = f"market:{market_id}"
    else:
        market = str(market_id) if market_id else "market:2"
    
    # Determine source (maker or hedger/taker)
    source = "maker" if role == "maker" else "hedger"
    
    # Create FillRecord format
    fill_record = {
        "type": "fill",
        "timestamp": timestamp,
        "market": market,
        "source": source,
        "role": role,
        "side": side,
        "price": str(price),
        "size": str(size),
        "base_delta": str(base_delta),
        "quote_delta": str(quote_delta),
        "notional": str(notional),
        "fee_paid": str(fee_paid),
        "mid_price": None,  # Not available in trade data
    }
    
    return fill_record


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert API trades to MetricsLedger format")
    parser.add_argument("--input", type=Path, required=True, help="Input JSONL file from query_api_history_v2.py")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL file in MetricsLedger format")
    parser.add_argument("--account", type=int, help="Account index (default: from env or 366110)")
    
    args = parser.parse_args()
    
    import os
    account_index = args.account or int(os.getenv("ACCOUNT_INDEX") or os.getenv("API_ACCOUNT_INDEX") or 366110)
    
    print(f"Converting API trades to MetricsLedger format...")
    print(f"Account: {account_index}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print()
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    count = 0
    converted = 0
    skipped = 0
    
    with args.input.open("r") as infile, args.output.open("w") as outfile:
        for line in infile:
            if not line.strip():
                continue
            
            try:
                trade = json.loads(line)
                count += 1
                
                fill_record = convert_trade_to_fill_record(trade, account_index)
                if fill_record:
                    outfile.write(json.dumps(fill_record) + "\n")
                    converted += 1
                else:
                    skipped += 1
                    
                if count % 1000 == 0:
                    print(f"Processed {count} trades, converted {converted}, skipped {skipped}...")
                    
            except Exception as e:
                print(f"Error processing trade {count}: {e}")
                skipped += 1
    
    print(f"\n✅ Conversion complete!")
    print(f"  Total trades: {count}")
    print(f"  Converted: {converted}")
    print(f"  Skipped: {skipped}")
    print(f"  Output: {args.output}")


if __name__ == "__main__":
    main()

