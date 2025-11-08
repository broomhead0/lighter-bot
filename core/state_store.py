# core/state_store.py
from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from modules.funding_optimizer import PairMetrics


class StateStore:
    """
    Tracks:
      - live mids (and synthetic mids)
      - optimizer state (active_pairs, pair metrics)
      - inventory (per-market position)
      - open orders
    """

    def __init__(self):
        self._mids: Dict[str, float] = {}
        self._synthetic_mids: Dict[str, float] = {}

        # M6 optimizer state
        self._active_pairs: List[str] = []
        self._pair_metrics: Dict[str, PairMetrics] = {}

        # Account info
        self._account_index: Optional[str] = None

        # Inventory tracking (per-market position in base units)
        self._inventory: Dict[str, Decimal] = {}  # market_id -> position

        # Order tracking
        self._open_orders: Dict[str, Dict[str, Any]] = {}  # order_id -> order info

        # Fee & volume stats
        self._volume_stats = {
            "maker_notional": Decimal("0"),
            "taker_notional": Decimal("0"),
            "maker_fee_actual": Decimal("0"),
            "maker_fee_premium": Decimal("0"),
            "taker_fee_actual": Decimal("0"),
            "taker_fee_premium": Decimal("0"),
            "hedger_notional": Decimal("0"),
            "hedger_fee_premium": Decimal("0"),
        }
        self._fill_counts = {
            "maker": 0,
            "taker": 0,
        }
        self._pnl_stats = {
            "maker_edge": Decimal("0"),
            "taker_slippage": Decimal("0"),
        }

    # -------- Mids ----------
    def set_mid(self, market_id: str, price: float) -> None:
        self._mids[market_id] = float(price)

    def update_mid(self, market_id: str, price: Union[float, Decimal]) -> None:
        """Update mid price, accepting Decimal or float (for router compatibility)."""
        if isinstance(price, Decimal):
            self._mids[market_id] = float(price)
        else:
            self._mids[market_id] = float(price)

    def get_mid(self, market_id: str) -> Optional[float]:
        return self._mids.get(market_id)

    def set_synthetic_mid(self, market_id: str, price: float) -> None:
        self._synthetic_mids[market_id] = float(price)

    def get_synthetic_mid(self, market_id: str) -> Optional[float]:
        return self._synthetic_mids.get(market_id)

    # -------- Optimizer ----------
    def set_active_pairs(self, pairs: List[str]) -> None:
        self._active_pairs = list(pairs or [])

    def get_active_pairs(self) -> List[str]:
        return list(self._active_pairs)

    def set_pair_metrics(self, metrics: Dict[str, PairMetrics]) -> None:
        self._pair_metrics = dict(metrics or {})

    def get_pair_metrics(self) -> Dict[str, PairMetrics]:
        return dict(self._pair_metrics)

    # -------- Account ----------
    def set_account_index(self, account_index: Optional[str]) -> None:
        self._account_index = str(account_index) if account_index is not None else None

    def get_account_index(self) -> Optional[str]:
        return self._account_index

    # -------- Inventory ----------
    def get_inventory(self, market_id: Optional[str] = None) -> Union[Decimal, Dict[str, Decimal]]:
        """Get inventory for a specific market, or all markets if None."""
        if market_id is None:
            return dict(self._inventory)
        return self._inventory.get(market_id, Decimal("0"))

    def update_inventory(self, market_id: str, delta: Decimal) -> None:
        """Update inventory by delta (positive for long, negative for short)."""
        if market_id not in self._inventory:
            self._inventory[market_id] = Decimal("0")
        self._inventory[market_id] += Decimal(str(delta))

    def set_inventory(self, market_id: str, value: Decimal) -> None:
        """Set absolute inventory value."""
        self._inventory[market_id] = Decimal(str(value))

    # -------- Orders ----------
    def add_order(self, order_id: str, order_info: Dict[str, Any]) -> None:
        """Add an open order."""
        self._open_orders[order_id] = dict(order_info)

    def remove_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Remove an order and return its info."""
        return self._open_orders.pop(order_id, None)

    def get_orders(self, market_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get all orders, optionally filtered by market."""
        if market_id is None:
            return dict(self._open_orders)
        return {
            oid: info
            for oid, info in self._open_orders.items()
            if info.get("market") == market_id
        }

    # -------- Fee & volume stats ----------
    def record_volume_sample(
        self,
        role: str,
        notional: Decimal,
        fee_actual: Decimal,
        fee_premium: Decimal,
    ) -> None:
        role_key = role.lower()
        if role_key == "maker":
            self._volume_stats["maker_notional"] += Decimal(str(notional))
            self._volume_stats["maker_fee_actual"] += Decimal(str(fee_actual))
            self._volume_stats["maker_fee_premium"] += Decimal(str(fee_premium))
            self._fill_counts["maker"] += 1
        elif role_key == "taker":
            self._volume_stats["taker_notional"] += Decimal(str(notional))
            self._volume_stats["taker_fee_actual"] += Decimal(str(fee_actual))
            self._volume_stats["taker_fee_premium"] += Decimal(str(fee_premium))
            self._fill_counts["taker"] += 1

    def record_hedger_simulation(self, notional: Decimal, fee_premium: Decimal) -> None:
        self._volume_stats["hedger_notional"] += Decimal(str(notional))
        self._volume_stats["hedger_fee_premium"] += Decimal(str(fee_premium))

    def get_fee_stats(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for key, value in self._volume_stats.items():
            out[key] = float(value)
        out["maker_fill_count"] = float(self._fill_counts["maker"])
        out["taker_fill_count"] = float(self._fill_counts["taker"])
        return out

    def record_maker_edge(self, value: Decimal) -> None:
        self._pnl_stats["maker_edge"] += Decimal(str(value))

    def record_taker_slippage(self, value: Decimal) -> None:
        self._pnl_stats["taker_slippage"] += Decimal(str(value))

    def get_pnl_stats(self) -> Dict[str, float]:
        return {key: float(val) for key, val in self._pnl_stats.items()}

    # -------- Time ----------
    def now(self) -> float:
        return time.time()
