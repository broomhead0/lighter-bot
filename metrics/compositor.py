from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Iterable, Optional, Tuple

from .ledger import FillEvent, MetricsLedger


DecimalZero = Decimal("0")


@dataclass
class MetricsSnapshot:
    realized_quote: Decimal = DecimalZero
    fees_paid: Decimal = DecimalZero
    maker_volume: Decimal = DecimalZero
    taker_volume: Decimal = DecimalZero
    hedger_volume: Decimal = DecimalZero
    fills: int = 0
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None
    inventory: Dict[str, Decimal] = field(default_factory=dict)
    unrealized_quote: Decimal = DecimalZero
    total_quote: Decimal = DecimalZero

    def as_dict(self, prefix: str = "") -> Dict[str, float]:
        data = {
            f"{prefix}realized_quote": float(self.realized_quote),
            f"{prefix}fees_paid": float(self.fees_paid),
            f"{prefix}maker_volume": float(self.maker_volume),
            f"{prefix}taker_volume": float(self.taker_volume),
            f"{prefix}hedger_volume": float(self.hedger_volume),
            f"{prefix}fills": float(self.fills),
            f"{prefix}unrealized_quote": float(self.unrealized_quote),
            f"{prefix}total_quote": float(self.total_quote),
        }
        for market, value in self.inventory.items():
            data[f"{prefix}inventory_{market.replace(':', '_')}"] = float(value)
        if self.start_ts is not None:
            data[f"{prefix}start_ts"] = float(self.start_ts)
        if self.end_ts is not None:
            data[f"{prefix}end_ts"] = float(self.end_ts)
        return data


class MetricsCompositor:
    """
    Compose metrics snapshots from a :class:`MetricsLedger`.
    """

    def __init__(self, ledger: MetricsLedger, *, mid_provider: Optional[callable] = None):
        self.ledger = ledger
        self.mid_provider = mid_provider

    def snapshot(
        self,
        *,
        window_seconds: Optional[float] = None,
        mids_override: Optional[Dict[str, float]] = None,
    ) -> MetricsSnapshot:
        now = time.time()
        since_ts = None
        if window_seconds is not None:
            since_ts = now - window_seconds
        events = list(self.ledger.iter_events(since_ts=since_ts))
        return self._compute(events, mids_override=mids_override)

    def _compute(
        self,
        events: Iterable[FillEvent],
        *,
        mids_override: Optional[Dict[str, float]] = None,
    ) -> MetricsSnapshot:
        snapshot = MetricsSnapshot()
        inventory: Dict[str, Decimal] = {}
        last_mid: Dict[str, Decimal] = {}

        for event in events:
            numbers = event.as_decimals()
            notional = numbers["notional"]
            quote_delta = numbers["quote_delta"]
            fee_paid = numbers["fee_paid"]
            base_delta = numbers["base_delta"]

            snapshot.fills += 1
            if snapshot.start_ts is None or event.timestamp < snapshot.start_ts:
                snapshot.start_ts = event.timestamp
            if snapshot.end_ts is None or event.timestamp > snapshot.end_ts:
                snapshot.end_ts = event.timestamp

            snapshot.realized_quote += quote_delta - fee_paid
            snapshot.fees_paid += fee_paid

            if event.role.lower() == "maker":
                snapshot.maker_volume += abs(notional)
            elif event.role.lower() == "taker":
                snapshot.taker_volume += abs(notional)
            elif event.source.startswith("hedger"):
                snapshot.hedger_volume += abs(notional)

            inventory[event.market] = inventory.get(event.market, DecimalZero) + base_delta
            if numbers["mid_price"] is not None:
                last_mid[event.market] = numbers["mid_price"]
            else:
                last_mid[event.market] = numbers["price"]

        snapshot.inventory = inventory
        snapshot.unrealized_quote = self._mark_to_market(
            inventory,
            last_mid,
            mids_override=mids_override,
        )
        snapshot.total_quote = snapshot.realized_quote + snapshot.unrealized_quote
        return snapshot

    def _mark_to_market(
        self,
        inventory: Dict[str, Decimal],
        last_mid: Dict[str, Decimal],
        *,
        mids_override: Optional[Dict[str, float]] = None,
    ) -> Decimal:
        unrealized = DecimalZero
        for market, base in inventory.items():
            if base == 0:
                continue
            mid = None
            if mids_override and market in mids_override:
                mid = Decimal(str(mids_override[market]))
            elif self.mid_provider:
                try:
                    mid_val = self.mid_provider(market)
                    if mid_val is not None:
                        mid = Decimal(str(mid_val))
                except Exception:
                    mid = None
            if mid is None:
                mid = last_mid.get(market, DecimalZero)
            unrealized += base * mid
        return unrealized

