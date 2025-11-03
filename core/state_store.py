# core/state_store.py
from __future__ import annotations

import time
from typing import Dict, List, Optional

from modules.funding_optimizer import PairMetrics


class StateStore:
    """
    Tracks:
      - live mids (and synthetic mids)
      - optimizer state (active_pairs, pair metrics)
    """

    def __init__(self):
        self._mids: Dict[str, float] = {}
        self._synthetic_mids: Dict[str, float] = {}

        # M6 optimizer state
        self._active_pairs: List[str] = []
        self._pair_metrics: Dict[str, PairMetrics] = {}

    # -------- Mids ----------
    def set_mid(self, market_id: str, price: float) -> None:
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

    # -------- Time ----------
    def now(self) -> float:
        return time.time()
