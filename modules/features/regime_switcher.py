from __future__ import annotations

"""
Regime Switcher Feature Module (stub)

Extracted from maker_engine.py to allow independent enable/disable.
Determines aggressive/defensive profiles based on guard/trend/volatility signals.

Phase 0 note: Provide interface and safe defaults; caller may ignore.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class RegimeProfile:
    size_multiplier: float
    extra_spread_bps: float
    down_cooldown_seconds: float


class RegimeSwitcher:
    def __init__(self, config: dict):
        self.enabled = bool((config or {}).get("enabled", False))
        self.min_dwell_seconds = float((config or {}).get("min_dwell_seconds", 60))
        self.vol_threshold_bps = float((config or {}).get("vol_threshold_bps", 6.0))
        self.profiles: Dict[str, RegimeProfile] = {
            "aggressive": RegimeProfile(1.0, 0.0, 20.0),
            "defensive": RegimeProfile(0.7, 2.0, 60.0),
        }
        self.current = "aggressive"

    def choose(self, *, pnl_guard_active: bool, trend_down: bool, low_vol: bool) -> str:
        if not self.enabled:
            return self.current
        target = "defensive" if (pnl_guard_active or trend_down or low_vol) else "aggressive"
        self.current = target
        return self.current

    def get_profile(self, name: str | None = None) -> RegimeProfile:
        key = name or self.current
        return self.profiles.get(key, self.profiles["aggressive"])
