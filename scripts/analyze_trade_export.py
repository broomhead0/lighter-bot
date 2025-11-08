#!/usr/bin/env python3
"""
Utility helper to reconcile UI trade exports with internal telemetry.

Usage:
    python scripts/analyze_trade_export.py /path/to/trade-export.csv
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Iterable, List

getcontext().prec = 28


@dataclass
class TradeSample:
    role: str
    side: str
    price: Decimal
    size: Decimal
    closed_pnl: Decimal
    trade_value: Decimal
    timestamp: str

    @property
    def notional(self) -> Decimal:
        return self.size * self.price


def parse_trade_export(path: Path) -> Iterable[TradeSample]:
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            closed = row.get("Closed PnL", "").strip()
            yield TradeSample(
                role=row.get("Role", "").strip().lower(),
                side=row.get("Side", "").strip(),
                price=Decimal(row["Price"]),
                size=Decimal(row["Size"]),
                closed_pnl=Decimal("0") if closed in ("", "-") else Decimal(closed),
                trade_value=Decimal(row["Trade Value"]),
                timestamp=row.get("Date", ""),
            )


def summarise_trades(trades: Iterable[TradeSample]) -> None:
    maker_pnl = Decimal("0")
    taker_pnl = Decimal("0")
    maker_notional = Decimal("0")
    taker_notional = Decimal("0")
    maker_count = 0
    taker_count = 0

    net_position = Decimal("0")
    avg_entry = Decimal("0")
    last_price = Decimal("0")

    worst_losses: List[TradeSample] = []
    best_wins: List[TradeSample] = []

    def track_extremes(container: List[TradeSample], sample: TradeSample, limit: int, reverse: bool) -> None:
        container.append(sample)
        container.sort(key=lambda t: t.closed_pnl, reverse=reverse)
        if len(container) > limit:
            container.pop(-1)

    for trade in trades:
        last_price = trade.price

        if trade.role == "maker":
            maker_pnl += trade.closed_pnl
            maker_notional += trade.trade_value
            maker_count += 1
        elif trade.role == "taker":
            taker_pnl += trade.closed_pnl
            taker_notional += trade.trade_value
            taker_count += 1

        side = trade.side.lower()

        delta = Decimal("0")
        if "open long" in side or "long > short" in side:
            delta = trade.size
        elif "close long" in side or "short > long" in side:
            delta = -trade.size
        elif "open short" in side:
            delta = -trade.size
        elif "close short" in side:
            delta = trade.size

        if delta != 0:
            prev_position = net_position
            new_position = net_position + delta

            if prev_position == 0:
                avg_entry = trade.price
            elif prev_position > 0 and new_position > 0:
                avg_entry = (
                    (avg_entry * prev_position) + (trade.price * delta)
                ) / new_position
            elif prev_position < 0 and new_position < 0:
                avg_entry = (
                    (avg_entry * (-prev_position)) + (trade.price * (-delta))
                ) / (-new_position)
            elif prev_position > 0 and new_position <= 0:
                avg_entry = Decimal("0") if new_position == 0 else trade.price
            elif prev_position < 0 and new_position >= 0:
                avg_entry = Decimal("0") if new_position == 0 else trade.price

            net_position = new_position

        if trade.closed_pnl < Decimal("0"):
            track_extremes(worst_losses, trade, limit=10, reverse=False)
        elif trade.closed_pnl > Decimal("0"):
            track_extremes(best_wins, trade, limit=10, reverse=True)

    realized_pnl = maker_pnl + taker_pnl
    mtm = Decimal("0")
    if net_position > 0 and last_price != 0:
        mtm = (last_price - avg_entry) * net_position
    elif net_position < 0 and last_price != 0:
        mtm = (avg_entry - last_price) * (-net_position)

    print("== Summary ==")
    print(f"Maker PnL:            ${maker_pnl:.6f} across {maker_count} fills")
    print(f"Taker slippage:       ${taker_pnl:.6f} across {taker_count} fills")
    print(f"Realized PnL:         ${realized_pnl:.6f}")
    print(f"Net position (units): {net_position:.6f} @ last price {last_price}")
    print(f"Mark-to-market:       ${mtm:.6f}")
    print(f"Net PnL:              ${(realized_pnl + mtm):.6f}")
    print(f"Maker notional:       ${maker_notional:.2f}")
    print(f"Taker notional:       ${taker_notional:.2f}")
    if maker_notional:
        print(f" Maker edge per $:    {maker_pnl / maker_notional:.8f}")
    if taker_notional:
        print(f" Taker drag per $:    {taker_pnl / taker_notional:.8f}")

    if worst_losses:
        print("\nWorst taker losses (top 5):")
        for sample in worst_losses[:5]:
            print(
                f" {sample.timestamp} {sample.side:15s} price={sample.price} pnl=${sample.closed_pnl}"
            )
    if best_wins:
        print("\nBest maker/taker wins (top 5):")
        for sample in best_wins[:5]:
            print(
                f" {sample.timestamp} {sample.side:15s} price={sample.price} pnl=${sample.closed_pnl}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Lighter trade export CSV.")
    parser.add_argument(
        "path",
        type=Path,
        help="Path to trade export (CSV)",
    )
    args = parser.parse_args()
    if not args.path.exists():
        raise SystemExit(f"File not found: {args.path}")
    summarise_trades(parse_trade_export(args.path))


if __name__ == "__main__":
    main()

