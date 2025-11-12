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

    for event in ledger.iter_events():
        if market_filter and event.market != market_filter:
            continue
        bucket = int(event.timestamp // window_seconds) * window_seconds
        entry = buckets[bucket]
        numbers = event.as_decimals()

        entry["realized_quote"] += numbers["quote_delta"] - numbers["fee_paid"]
        entry["fees_paid"] += numbers["fee_paid"]
        entry["notional_abs"] += abs(numbers["notional"])
        entry["base_delta"] += numbers["base_delta"]
        entry["hedger_volume"] += abs(numbers["notional"]) if event.source.startswith("hedger") else Decimal("0")
        if event.role.lower() == "maker":
            entry["maker_volume"] += abs(numbers["notional"])
        elif event.role.lower() == "taker":
            entry["taker_volume"] += abs(numbers["notional"])

        # Track first/last timestamps for readability
        meta_bucket = meta[bucket]
        if "start_ts" not in meta_bucket or event.timestamp < meta_bucket["start_ts"]:
            meta_bucket["start_ts"] = event.timestamp
        if "end_ts" not in meta_bucket or event.timestamp > meta_bucket["end_ts"]:
            meta_bucket["end_ts"] = event.timestamp
        meta_bucket["market"] = event.market
        meta_bucket["fill_count"] = meta_bucket.get("fill_count", 0) + 1

    rows: List[Mapping[str, object]] = []
    for bucket in sorted(buckets.keys()):
        entry = buckets[bucket]
        info = meta[bucket]
        rows.append(
            {
                "bucket_start_ts": bucket,
                "window_seconds": window_seconds,
                "start_ts": int(info.get("start_ts", bucket)),
                "end_ts": int(info.get("end_ts", bucket + window_seconds)),
                "market": info.get("market"),
                "fill_count": info.get("fill_count", 0),
                "realized_quote": float(entry["realized_quote"]),
                "fees_paid": float(entry["fees_paid"]),
                "maker_volume": float(entry.get("maker_volume", Decimal("0"))),
                "taker_volume": float(entry.get("taker_volume", Decimal("0"))),
                "hedger_volume": float(entry.get("hedger_volume", Decimal("0"))),
                "notional_abs": float(entry["notional_abs"]),
                "base_delta": float(entry["base_delta"]),
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


