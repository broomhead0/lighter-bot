# modules/mock_metrics.py
from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass
from typing import List

from modules.funding_optimizer import FundingDataSource, PairMetrics


@dataclass
class MockMarket:
    market_id: str
    symbol: str
    base_mid: float
    amp_funding_8h: float
    amp_oi: float
    base_spread_bps: float


class MockMetricsProvider(FundingDataSource):
    """
    Deterministic-ish, time-varying metrics so you can watch rotations:
      - funding_8h oscillates with different phases
      - open_interest oscillates with different amplitudes
      - spread_bps has light noise
    """

    def __init__(self, markets: List[MockMarket]):
        self._mkts = markets
        self._t0 = time.time()

    async def fetch_pair_metrics(self) -> List[PairMetrics]:
        now = time.time() - self._t0
        out: List[PairMetrics] = []
        for i, m in enumerate(self._mkts):
            phase = 0.7 * i
            funding_8h = m.amp_funding_8h * math.sin(now * 0.08 + phase)
            oi = abs(m.amp_oi * math.sin(now * 0.05 + 1.2 * i)) + m.amp_oi * 0.3
            spread_bps = max(1.0, m.base_spread_bps + random.uniform(-1.0, 1.0))
            out.append(
                PairMetrics(
                    market_id=m.market_id,
                    symbol=m.symbol,
                    funding_8h=funding_8h,
                    open_interest=oi,
                    spread_bps=spread_bps,
                    vol24h=None,
                )
            )
        await asyncio.sleep(0.05)
        return out
