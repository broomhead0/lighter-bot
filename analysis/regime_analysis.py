#!/usr/bin/env python3
"""
Lightweight regime analysis to understand how realized PnL behaves versus market conditions.

Example:
    PYTHONPATH=. python analysis/regime_analysis.py \
        --pnl-csv data/analysis/pnl_5m.csv \
        --candles-json data/analysis/binance_solusdt_1m.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence


@dataclass
class PnLWindow:
    bucket_start_ts: int
    window_seconds: int
    realized_quote: float
    maker_volume: float
    base_delta: float


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float


@dataclass
class RegimeRow:
    pnl: PnLWindow
    price_return: float
    abs_return: float
    range_ratio: float
    vol: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Correlate PnL windows with SOL market regimes.")
    parser.add_argument("--pnl-csv", type=Path, required=True, help="CSV produced by export_pnl_windows.py")
    parser.add_argument("--candles-json", type=Path, required=True, help="JSON list of 1m candles")
    parser.add_argument(
        "--window-seconds",
        type=int,
        default=300,
        help="Window size for the PnL CSV (default: 300 seconds = 5 minutes).",
    )
    parser.add_argument(
        "--min-candles",
        type=int,
        default=3,
        help="Require at least this many candles in a window to compute features (default: 3).",
    )
    return parser.parse_args()


def load_pnl_windows(path: Path) -> Sequence[PnLWindow]:
    rows: List[PnLWindow] = []
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(
                PnLWindow(
                    bucket_start_ts=int(float(row["bucket_start_ts"])),
                    window_seconds=int(row["window_seconds"]),
                    realized_quote=float(row["realized_quote"]),
                    maker_volume=float(row["maker_volume"]),
                    base_delta=float(row["base_delta"]),
                )
            )
    return rows


def load_candles(path: Path) -> Sequence[Candle]:
    candles: List[Candle] = []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    for row in data:
        candles.append(
            Candle(
                open_time=int(row["open_time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            )
        )
    candles.sort(key=lambda c: c.open_time)
    return candles


def slice_candles(
    candles: Sequence[Candle], start_ms: int, end_ms: int
) -> Sequence[Candle]:
    window: List[Candle] = []
    for candle in candles:
        if candle.open_time >= end_ms:
            break
        if start_ms <= candle.open_time < end_ms:
            window.append(candle)
    return window


def coalesce_windows(pnl_windows: Sequence[PnLWindow], window_ms: int) -> Sequence[PnLWindow]:
    aggregates: Dict[int, Dict[str, float]] = defaultdict(lambda: {"realized": 0.0, "volume": 0.0, "base": 0.0})
    for pnl in pnl_windows:
        bucket_start = (pnl.bucket_start_ts // window_ms) * window_ms
        agg = aggregates[bucket_start]
        agg["realized"] += pnl.realized_quote
        agg["volume"] += pnl.maker_volume
        agg["base"] += pnl.base_delta

    coalesced: List[PnLWindow] = []
    for bucket_start in sorted(aggregates.keys()):
        agg = aggregates[bucket_start]
        coalesced.append(
            PnLWindow(
                bucket_start_ts=bucket_start,
                window_seconds=window_ms // 1000,
                realized_quote=agg["realized"],
                maker_volume=agg["volume"],
                base_delta=agg["base"],
            )
        )
    return coalesced


def compute_regime_rows(
    pnl_windows: Sequence[PnLWindow],
    candles: Sequence[Candle],
    window_seconds: int,
    min_candles: int,
) -> Sequence[RegimeRow]:
    rows: List[RegimeRow] = []
    window_ms = window_seconds * 1000
    coalesced = coalesce_windows(pnl_windows, window_ms)

    for pnl in coalesced:
        start_ms = pnl.bucket_start_ts
        end_ms = start_ms + window_ms
        bucket_candles = slice_candles(candles, start_ms, end_ms)
        if len(bucket_candles) < min_candles:
            continue

        first = bucket_candles[0]
        last = bucket_candles[-1]
        open_price = first.open
        close_price = last.close
        if open_price <= 0 or close_price <= 0:
            continue

        price_return = (close_price / open_price) - 1.0
        abs_return = abs(price_return)
        high = max(c.high for c in bucket_candles)
        low = min(c.low for c in bucket_candles)
        range_ratio = (high - low) / open_price if open_price else 0.0

        minute_returns: List[float] = []
        prev_close = first.close
        for candle in bucket_candles[1:]:
            if prev_close > 0:
                minute_returns.append((candle.close / prev_close) - 1.0)
            prev_close = candle.close
        vol = statistics.pstdev(minute_returns) if len(minute_returns) > 1 else 0.0

        rows.append(
            RegimeRow(
                pnl=pnl,
                price_return=price_return,
                abs_return=abs_return,
                range_ratio=range_ratio,
                vol=vol,
            )
        )
    return rows


def pearson(xs: Iterable[float], ys: Iterable[float]) -> float:
    xs_list = list(xs)
    ys_list = list(ys)
    if len(xs_list) != len(ys_list) or len(xs_list) == 0:
        return math.nan
    mean_x = statistics.fmean(xs_list)
    mean_y = statistics.fmean(ys_list)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs_list, ys_list))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs_list))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys_list))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def quantile_splits(values: Sequence[float], buckets: int) -> List[float]:
    if not values:
        return []
    sorted_vals = sorted(values)
    splits: List[float] = []
    for i in range(1, buckets):
        idx = int(len(sorted_vals) * i / buckets)
        splits.append(sorted_vals[min(idx, len(sorted_vals) - 1)])
    return splits


def bucketize(value: float, splits: Sequence[float]) -> int:
    for i, split in enumerate(splits):
        if value <= split:
            return i
    return len(splits)


def summarize(rows: Sequence[RegimeRow]) -> None:
    if not rows:
        print("No overlapping windows between PnL data and candles.")
        return

    pnl_values = [row.pnl.realized_quote for row in rows]
    print(f"Matched windows: {len(rows)}")
    print(f"Avg realized PnL (quote): {statistics.fmean(pnl_values):.4f}")
    print(f"Median realized PnL (quote): {statistics.median(pnl_values):.4f}")

    correlations = {
        "price_return": pearson(pnl_values, [row.price_return for row in rows]),
        "abs_return": pearson(pnl_values, [row.abs_return for row in rows]),
        "range_ratio": pearson(pnl_values, [row.range_ratio for row in rows]),
        "vol": pearson(pnl_values, [row.vol for row in rows]),
        "base_delta": pearson(pnl_values, [row.pnl.base_delta for row in rows]),
    }
    print("Correlations (realized PnL vs feature):")
    for key, value in correlations.items():
        print(f"  {key:>12}: {value: .3f}")

    def summarize_group(name: str, predicate) -> None:
        group = [row.pnl.realized_quote for row in rows if predicate(row)]
        if group:
            print(f"{name:<24} count={len(group):4d} avg={statistics.fmean(group): .4f}")

    summarize_group("Up trend (>0.1%)", lambda r: r.price_return > 0.001)
    summarize_group("Down trend (<-0.1%)", lambda r: r.price_return < -0.001)
    summarize_group("Flat trend", lambda r: abs(r.price_return) <= 0.001)

    vol_values = [row.vol for row in rows]
    splits = quantile_splits(vol_values, buckets=3)
    buckets_summary = [[] for _ in range(len(splits) + 1)]
    for row in rows:
        idx = bucketize(row.vol, splits)
        buckets_summary[idx].append(row.pnl.realized_quote)

    for idx, group in enumerate(buckets_summary):
        if not group:
            continue
        if idx == 0:
            label = f"Low vol (≤ {splits[idx]:.4f})" if splits else "Low vol"
        elif idx == len(buckets_summary) - 1:
            label = f"High vol (> {splits[idx-1]:.4f})"
        else:
            label = f"Mid vol (≤ {splits[idx]:.4f})"
        print(f"{label:<24} count={len(group):4d} avg={statistics.fmean(group): .4f}")


def main() -> None:
    args = parse_args()
    pnl_windows = load_pnl_windows(args.pnl_csv)
    candles = load_candles(args.candles_json)
    rows = compute_regime_rows(pnl_windows, candles, args.window_seconds, args.min_candles)
    summarize(rows)


if __name__ == "__main__":
    main()


