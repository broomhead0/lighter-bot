from __future__ import annotations

"""
Volatility Adjustments Feature Module

Extracted from maker_engine.py to allow independent enable/disable.
Provides EMA-based volatility estimate, pause flags and optional spread/size modifiers.

Phase 0 note: Keep behavior parity; expose data without enforcing changes.
"""

import math
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class VolatilityState:
    ema_bps: float = 0.0
    last_mid: Optional[float] = None
    last_ts: float = 0.0
    paused_high: bool = False
    paused_low: bool = False


class VolatilityAdjustments:
    def __init__(self, config: dict):
        self.enabled = bool((config or {}).get("enabled", False))
        cfg = config or {}
        self.low_bps = float(cfg.get("low_bps", 5.0))
        self.high_bps = float(cfg.get("high_bps", 25.0))
        self.min_spread_bps = float(cfg.get("min_spread_bps", 10.0))
        self.max_spread_bps = float(cfg.get("max_spread_bps", 20.0))
        self.high_vol_threshold_bps = float(cfg.get("high_vol_threshold_bps", 0.0))
        self.low_vol_pause_threshold_bps = float(cfg.get("low_vol_pause_threshold_bps", 0.0))
        self.low_vol_resume_threshold_bps = float(cfg.get("low_vol_resume_threshold_bps", 0.0))
        self.resume_inventory_ratio = float(cfg.get("resume_inventory_ratio", 0.25))
        self.halflife_seconds = max(float(cfg.get("ema_halflife_seconds", 30.0)), 1.0)

        self.state = VolatilityState()

    def update_and_get_bps(self, mid: Optional[float]) -> float:
        if not self.enabled or mid is None:
            return float(self.state.ema_bps or 0.0)
        now = time.time()
        if self.state.last_mid is None:
            self.state.last_mid = mid
            self.state.last_ts = now
            self.state.ema_bps = 0.0
            return 0.0
        dt = max(now - self.state.last_ts, 1e-6)
        change = abs(mid - self.state.last_mid) / max(self.state.last_mid, 1e-9)
        change_bps = change * 10000.0
        alpha = 1 - math.exp(-math.log(2) * dt / self.halflife_seconds)
        prev = self.state.ema_bps or change_bps
        self.state.ema_bps = prev + alpha * (change_bps - prev)
        self.state.last_mid = mid
        self.state.last_ts = now
        return float(self.state.ema_bps)

    def get_spread_for_volatility(self, base_spread_bps: float) -> float:
        if not self.enabled:
            return base_spread_bps
        # Map ema_bps into [min_spread, max_spread]
        factor = 0.0
        if self.high_bps > self.low_bps:
            factor = (self.state.ema_bps - self.low_bps) / (self.high_bps - self.low_bps)
            factor = max(0.0, min(1.0, factor))
        spread_span = self.max_spread_bps - self.min_spread_bps
        return self.min_spread_bps + spread_span * factor

    def get_pause_flags(self, can_resume: bool = True) -> tuple[bool, bool]:
        # High-vol pause left to caller; expose low-vol pause mimic
        paused_low = False
        if self.low_vol_pause_threshold_bps > 0.0 and self.state.ema_bps <= self.low_vol_pause_threshold_bps and self.state.ema_bps > 0.0:
            paused_low = True
        if paused_low and can_resume and self.low_vol_resume_threshold_bps > 0.0 and self.state.ema_bps >= self.low_vol_resume_threshold_bps:
            paused_low = False
        self.state.paused_low = paused_low
        return self.state.paused_high, self.state.paused_low
