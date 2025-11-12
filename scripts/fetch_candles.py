#!/usr/bin/env python3
"""
Fetch OHLCV candles for a Lighter market (e.g. SOL `market:2`) and save to JSON or CSV.

Usage examples:
    python scripts/fetch_candles.py --market-id 2 --interval 1m --limit 1440 --output data/analysis/sol_1m.json
    python scripts/fetch_candles.py --market-id 2 --interval 5m --start-ts 1762800000 --output data/analysis/sol_5m.csv

The script defaults to the Lighter mainnet REST endpoint but accepts `--base-url` or the
`API_BASE_URL` environment variable for overrides.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import requests


def _default_base_url() -> str:
    return os.getenv("API_BASE_URL", "https://mainnet.zklighter.elliot.ai")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch OHLCV candles for a Lighter market.")
    parser.add_argument("--market-id", type=int, required=True, help="Lighter market id (e.g. 2 for SOL).")
    parser.add_argument(
        "--interval",
        type=str,
        default="1m",
        help="Candle interval (default: 1m). Must match Lighter API supported values.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum number of candles to fetch (default: 500, max per API call).",
    )
    parser.add_argument(
        "--start-ts",
        type=int,
        help="Optional start timestamp (ms since epoch). If set, candles after this timestamp are returned.",
    )
    parser.add_argument(
        "--end-ts",
        type=int,
        help="Optional end timestamp (ms since epoch). If set, candles before this timestamp are returned.",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=_default_base_url(),
        help="Override base REST URL (default: %(default)s or API_BASE_URL env var).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write results. Extension determines format (.json/.jsonl/.csv).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (ignored for CSV).",
    )
    return parser.parse_args()


def fetch_candles(
    base_url: str,
    market_id: int,
    interval: str,
    limit: int,
    start_ts: Optional[int],
    end_ts: Optional[int],
) -> Sequence[Mapping[str, object]]:
    url = f"{base_url.rstrip('/')}/public/markets/{market_id}/candles"
    params = {
        "interval": interval,
        "limit": limit,
    }
    if start_ts is not None:
        params["start_ts"] = start_ts
    if end_ts is not None:
        params["end_ts"] = end_ts

    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"Request failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    candles = data.get("candles") if isinstance(data, dict) else data
    if not isinstance(candles, list):
        raise SystemExit("Unexpected response format: missing candles array.")
    return candles


def _write_json(path: Path, candles: Iterable[Mapping[str, object]], pretty: bool) -> None:
    indent = 2 if pretty else None
    if path.suffix == ".jsonl":
        with path.open("w", encoding="utf-8") as fh:
            for candle in candles:
                fh.write(json.dumps(candle) + "\n")
        return
    with path.open("w", encoding="utf-8") as fh:
        json.dump(list(candles), fh, indent=indent)


def _write_csv(path: Path, candles: Iterable[Mapping[str, object]]) -> None:
    candles = list(candles)
    if not candles:
        path.touch()
        return
    fieldnames = list(candles[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candles)


def write_output(path: Path, candles: Sequence[Mapping[str, object]], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl"}:
        _write_json(path, candles, pretty)
    elif suffix == ".csv":
        _write_csv(path, candles)
    else:
        raise SystemExit(f"Unsupported output extension: {suffix}")


def main() -> None:
    args = parse_args()
    candles = fetch_candles(
        base_url=args.base_url,
        market_id=args.market_id,
        interval=args.interval,
        limit=args.limit,
        start_ts=args.start_ts,
        end_ts=args.end_ts,
    )
    write_output(args.output, candles, args.pretty)
    print(f"Wrote {len(candles)} candles to {args.output}")


if __name__ == "__main__":
    main()


