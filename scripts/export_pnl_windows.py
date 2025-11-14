#!/usr/bin/env python3
"""
Aggregate the metrics ledger into fixed windows (e.g. 5-minute slices) for downstream analysis.

Example:
    python scripts/export_pnl_windows.py --ledger data/metrics/fills.jsonl --window 300 \
        --output data/analysis/sol_pnl_5m.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

from metrics.ledger import MetricsLedger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate metrics ledger into fixed windows.")
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("data/metrics/fills.jsonl"),
        help="Path to ledger JSONL file (default: data/metrics/fills.jsonl).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=300,
        help="Window size in seconds (default: 300).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="CSV file to write aggregated data.",
    )
    parser.add_argument(
        "--market-id",
        type=str,
        default=None,
        help="Optional market id filter (e.g. 'market:2'). If omitted all markets are aggregated.",
    )
    return parser.parse_args()


def aggregate_windows(
    ledger: MetricsLedger,
    window_seconds: int,
    market_filter: str | None,
) -> List[Mapping[str, object]]:
    buckets: Dict[int, Dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    meta: Dict[int, Dict[str, object]] = defaultdict(dict)
    
    # Track FIFO lots per market for realized PnL calculation
    from collections import deque
    fifo_lots: Dict[str, deque] = defaultdict(deque)  # market -> deque of (size, price)
    inventory: Dict[str, Decimal] = defaultdict(Decimal)  # market -> inventory
    
    # Track last mid price per market for unrealized PnL
    last_mid: Dict[str, Decimal] = {}  # market -> last mid price

    for event in ledger.iter_events():
        if market_filter and event.market != market_filter:
            continue
        bucket = int(event.timestamp // window_seconds) * window_seconds
        entry = buckets[bucket]
        numbers = event.as_decimals()

        # Cash flow (original calculation)
        entry["realized_quote"] += numbers["quote_delta"] - numbers["fee_paid"]
        entry["fees_paid"] += numbers["fee_paid"]
        entry["notional_abs"] += abs(numbers["notional"])
        entry["base_delta"] += numbers["base_delta"]
        entry["hedger_volume"] += abs(numbers["notional"]) if event.source.startswith("hedger") else Decimal("0")
        if event.role.lower() == "maker":
            entry["maker_volume"] += abs(numbers["notional"])
        elif event.role.lower() == "taker":
            entry["taker_volume"] += abs(numbers["notional"])

        # Track inventory
        inventory[event.market] += numbers["base_delta"]
        entry["inventory_at_end"] = inventory[event.market]
        
        # Track mid price
        if numbers.get("mid_price") is not None:
            last_mid[event.market] = numbers["mid_price"]

        # Calculate FIFO realized PnL (only for maker fills)
        if event.role.lower() == "maker":
            lots = fifo_lots[event.market]
            base_delta = numbers["base_delta"]
            fill_price = numbers["price"]
            fee_actual = numbers["fee_paid"]
            realized = Decimal("0")

            if base_delta > 0:  # Buying (closing shorts or opening longs)
                remaining = base_delta
                while lots and lots[0][0] < 0 and remaining > 0:
                    short_lot = lots[0]
                    lot_size, lot_price = short_lot
                    matched = min(remaining, -lot_size)
                    realized += (lot_price - fill_price) * matched  # Profit when covering shorts
                    lot_size += matched  # lot_size is negative
                    remaining -= matched
                    if lot_size == 0:
                        lots.popleft()
                    else:
                        short_lot[0] = lot_size
                if remaining > 0:
                    lots.append([remaining, fill_price])  # Opening new long position
            elif base_delta < 0:  # Selling (closing longs or opening shorts)
                remaining = -base_delta
                while lots and lots[0][0] > 0 and remaining > 0:
                    long_lot = lots[0]
                    lot_size, lot_price = long_lot
                    matched = min(remaining, lot_size)
                    realized += (fill_price - lot_price) * matched  # Profit when closing longs
                    lot_size -= matched
                    remaining -= matched
                    if lot_size == 0:
                        lots.popleft()
                    else:
                        long_lot[0] = lot_size
                if remaining > 0:
                    lots.appendleft([-remaining, fill_price])  # Opening new short position

            realized -= fee_actual  # Subtract fees
            entry["fifo_realized_quote"] = entry.get("fifo_realized_quote", Decimal("0")) + realized

        # Track first/last timestamps for readability
        meta_bucket = meta[bucket]
        if "start_ts" not in meta_bucket or event.timestamp < meta_bucket["start_ts"]:
            meta_bucket["start_ts"] = event.timestamp
        if "end_ts" not in meta_bucket or event.timestamp > meta_bucket["end_ts"]:
            meta_bucket["end_ts"] = event.timestamp
        meta_bucket["market"] = event.market
        meta_bucket["fill_count"] = meta_bucket.get("fill_count", 0) + 1

    rows: List[Mapping[str, object]] = []
    cumulative_fifo_realized: Dict[str, Decimal] = defaultdict(Decimal)  # Track cumulative FIFO realized per market
    
    for bucket in sorted(buckets.keys()):
        entry = buckets[bucket]
        info = meta[bucket]
        market = info.get("market", "")
        
        # Get FIFO realized PnL for this window (delta from previous)
        fifo_realized_delta = float(entry.get("fifo_realized_quote", Decimal("0")))
        cumulative_fifo_realized[market] += Decimal(str(fifo_realized_delta))
        
        # Calculate unrealized PnL at end of window
        # unrealized = sum(lot_size * (current_mid - lot_cost_basis)) for all open lots
        unrealized = Decimal("0")
        if market in fifo_lots and market in last_mid:
            lots = fifo_lots[market]
            mid = last_mid.get(market, Decimal("0"))
            # Mark to market: calculate unrealized PnL on all open lots
            for lot_size, lot_price in lots:
                # lot_size is positive for longs, negative for shorts
                # For longs: unrealized = size * (mid - cost)
                # For shorts: unrealized = size * (cost - mid) = -size * (mid - cost)
                # Combined: unrealized = lot_size * (mid - lot_price)
                # But lot_size is positive for longs, negative for shorts, so:
                if lot_size > 0:  # Long position
                    unrealized += lot_size * (mid - lot_price)
                else:  # Short position (lot_size is negative)
                    unrealized += lot_size * (mid - lot_price)  # lot_size is negative, so this works
        
        # True PnL = FIFO realized + unrealized
        true_pnl = cumulative_fifo_realized[market] + unrealized
        
        rows.append(
            {
                "bucket_start_ts": bucket,
                "window_seconds": window_seconds,
                "start_ts": int(info.get("start_ts", bucket)),
                "end_ts": int(info.get("end_ts", bucket + window_seconds)),
                "market": market,
                "fill_count": info.get("fill_count", 0),
                "realized_quote": float(entry["realized_quote"]),  # Cash flow (deprecated)
                "fifo_realized_quote": float(cumulative_fifo_realized[market]),  # True FIFO realized PnL
                "unrealized_quote": float(unrealized),  # Unrealized PnL at end of window
                "true_pnl_quote": float(true_pnl),  # True PnL = FIFO realized + unrealized
                "fees_paid": float(entry["fees_paid"]),
                "maker_volume": float(entry.get("maker_volume", Decimal("0"))),
                "taker_volume": float(entry.get("taker_volume", Decimal("0"))),
                "hedger_volume": float(entry.get("hedger_volume", Decimal("0"))),
                "notional_abs": float(entry["notional_abs"]),
                "base_delta": float(entry["base_delta"]),
                "inventory_at_end": float(entry.get("inventory_at_end", Decimal("0"))),
            }
        )
    return rows


def write_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.touch()
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    ledger = MetricsLedger(args.ledger)
    rows = aggregate_windows(ledger, window_seconds=args.window, market_filter=args.market_id)
    write_csv(args.output, rows)
    print(f"Wrote {len(rows)} windows to {args.output}")


if __name__ == "__main__":
    main()


