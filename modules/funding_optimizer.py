# modules/funding_optimizer.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PairMetrics:
    market_id: str                   # canonical id, e.g. "market:1"
    symbol: Optional[str] = None     # optional human-readable, e.g. "BTC-PERP"
    funding_1h: Optional[float] = None    # decimal (0.0005 == 0.05% per hour)
    funding_8h: Optional[float] = None
    funding_24h: Optional[float] = None
    open_interest: Optional[float] = None # notional or units
    spread_bps: Optional[float] = None    # (ask-bid)/mid * 1e4
    vol24h: Optional[float] = None        # optional 24h volume


@dataclass(frozen=True)
class OptimizerConfig:
    scan_interval_s: int = 30
    top_n: int = 3
    min_open_interest: float = 0.0
    max_spread_bps: float = 25.0
    # scoring weights
    w_funding: float = 1.0
    w_oi: float = 0.2
    spread_bps_penalty: float = 0.02  # subtract (penalty * spread_bps)
    # rotation / stability controls
    min_dwell_s: int = 120
    hysteresis_score_margin: float = 0.05  # keep near-cutoff incumbents
    max_switches_per_hour: int = 12        # churn guard


class FundingDataSource:
    """Minimal protocol for a metrics provider (implemented by core.rest_client.RestClient)."""
    async def fetch_pair_metrics(self) -> List[PairMetrics]:
        raise NotImplementedError


class MakerPairsUpdater:
    """Minimal API for the maker engine to accept an updated active-pair set."""
    def update_active_pairs(self, market_ids: Sequence[str]) -> None:
        raise NotImplementedError


class StateStoreAdapter:
    """Minimal surface of StateStore used by the optimizer."""
    def set_active_pairs(self, pairs: Sequence[str]) -> None: ...
    def get_active_pairs(self) -> List[str]: ...
    def set_pair_metrics(self, metrics: Dict[str, PairMetrics]) -> None: ...
    def now(self) -> float: ...


class FundingOptimizer:
    """
    Periodically:
      1) fetch metrics
      2) score pairs
      3) choose top-N with hysteresis & churn guards
      4) notify Maker + StateStore
    """

    def __init__(
        self,
        data_source: FundingDataSource,
        state: StateStoreAdapter,
        maker_updater: MakerPairsUpdater,
        cfg: OptimizerConfig,
    ):
        self._ds = data_source
        self._state = state
        self._maker = maker_updater
        self._cfg = cfg

        self._last_switch_ts: float = 0.0
        self._switch_count_window: List[float] = []  # timestamps of recent switches
        self._last_scores: Dict[str, float] = {}      # score cache for hysteresis

        self._task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._run_loop(), name="FundingOptimizerLoop")
            logger.info("[optimizer] started.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("[optimizer] stopped.")

    async def _run_loop(self) -> None:
        interval = max(5, int(self._cfg.scan_interval_s))
        while self._running:
            try:
                await self._tick_once()
            except Exception as e:
                logger.exception("[optimizer] tick error: %s", e)
            await asyncio.sleep(interval)

    async def _tick_once(self) -> None:
        metrics_list = await self._safe_fetch_metrics()
        if not metrics_list:
            return

        metrics_by_id: Dict[str, PairMetrics] = {m.market_id: m for m in metrics_list}
        self._state.set_pair_metrics(metrics_by_id)

        scored: List[Tuple[str, float]] = []
        for m in metrics_list:
            s = self._score(m)
            scored.append((m.market_id, s))
        scored.sort(key=lambda kv: kv[1], reverse=True)

        chosen = self._choose_with_hysteresis(scored)
        current = self._state.get_active_pairs()

        if self._should_switch(current, chosen):
            self._apply_selection(chosen)

        self._last_scores = {mid: score for mid, score in scored}

    async def _safe_fetch_metrics(self) -> List[PairMetrics]:
        try:
            return await self._ds.fetch_pair_metrics()
        except NotImplementedError:
            logger.warning("[optimizer] data source not implemented; skipping fetch.")
            return []
        except Exception as e:
            logger.exception("[optimizer] fetch metrics error: %s", e)
            return []

    def _score(self, m: PairMetrics) -> float:
        # funding basis (normalize toward ~8h)
        if m.funding_8h is not None:
            funding = m.funding_8h
        elif m.funding_1h is not None:
            funding = m.funding_1h * 8.0
        elif m.funding_24h is not None:
            funding = m.funding_24h / 3.0
        else:
            funding = 0.0

        oi = m.open_interest or 0.0
        spread_pen = (m.spread_bps or 0.0) * self._cfg.spread_bps_penalty

        # hard filters become cliffs
        if oi < self._cfg.min_open_interest:
            return -1e9
        if (m.spread_bps or 0.0) > self._cfg.max_spread_bps:
            return -1e9

        score = self._cfg.w_funding * funding + self._cfg.w_oi * oi - spread_pen
        return float(score)

    def _choose_with_hysteresis(self, scored: List[Tuple[str, float]]) -> List[str]:
        top_n = max(1, int(self._cfg.top_n))
        raw = [mid for (mid, _) in scored[:top_n]]
        current = set(self._state.get_active_pairs() or [])
        if not current:
            return raw

        cutoff_score = scored[min(len(scored) - 1, top_n - 1)][1] if scored else -1e9
        margin = self._cfg.hysteresis_score_margin

        preserved = set(raw)
        for mid in current:
            last = self._last_scores.get(mid)
            if last is None:
                last = next((s for m, s in scored if m == mid), None)
            if last is None:
                continue
            if last + margin >= cutoff_score:
                preserved.add(mid)

        preserved_scored = sorted(
            [(mid, self._last_scores.get(mid, -1e9)) for mid in preserved],
            key=lambda kv: kv[1],
            reverse=True,
        )
        final = [mid for (mid, _) in preserved_scored[:top_n]]
        return final

    def _should_switch(self, current: Sequence[str], new: Sequence[str]) -> bool:
        cur_set, new_set = set(current or []), set(new or [])
        if cur_set == new_set:
            return False

        now = self._state.now()

        # dwell guard
        if now - self._last_switch_ts < self._cfg.min_dwell_s:
            return False

        # churn guard (switches/hour)
        one_hour_ago = now - 3600.0
        self._switch_count_window = [t for t in self._switch_count_window if t >= one_hour_ago]
        if len(self._switch_count_window) >= self._cfg.max_switches_per_hour:
            return False

        return True

    def _apply_selection(self, chosen: Sequence[str]) -> None:
        now = self._state.now()
        self._last_switch_ts = now
        self._switch_count_window.append(now)

        self._state.set_active_pairs(list(chosen))
        self._maker.update_active_pairs(list(chosen))
        logger.info("[optimizer] selected pairs: %s", list(chosen))
