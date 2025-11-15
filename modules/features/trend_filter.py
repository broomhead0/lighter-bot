"""
Trend Filter Feature Module

Extracted from maker_engine.py to allow independent enable/disable.
Provides trend detection and spread adjustments based on price movement.
"""

import logging
import time
from collections import deque
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

LOG = logging.getLogger("trend")


class TrendFilter:
    """
    Detects trends and adjusts quoting behavior.
    
    Current implementation uses simple price change over lookback window.
    Can be simplified further in future iterations.
    """
    
    def __init__(self, config: Dict[str, Any], state: Any = None, telemetry: Any = None):
        """
        Initialize trend filter.
        
        Args:
            config: Trend config section from config.yaml
            state: StateStore instance (for inventory access)
            telemetry: Telemetry instance (optional)
        """
        self.config = config
        self.state = state
        self.telemetry = telemetry
        self.enabled = config.get("enabled", False)
        
        if not self.enabled:
            return
        
        # Config parameters
        self.lookback_seconds = float(config.get("lookback_seconds", 45))
        self.threshold_bps = float(config.get("threshold_bps", 12))
        self.down_threshold_bps = float(config.get("down_threshold_bps", 4))
        self.resume_threshold_bps = float(config.get("resume_threshold_bps", 6))
        self.extra_spread_bps = float(config.get("extra_spread_bps", 2.5))
        self.down_extra_spread_bps = float(config.get("down_extra_spread_bps", 8.0))
        self.down_bias = config.get("down_bias", "ask")
        self.down_cooldown_seconds = float(config.get("down_cooldown_seconds", 60))
        self.inventory_soft_cap_ratio = float(config.get("inventory_soft_cap_ratio", 0.6))
        
        # State
        self._samples: deque = deque()  # (timestamp, mid_price)
        self._trend_state = "neutral"  # "neutral", "ask_only", "bid_only"
        self._trend_signal = "neutral"  # "neutral", "up", "down"
        self._downtrend_cooldown_until = 0.0
        
        # For inventory-aware decisions (will be set by maker_engine)
        self.inventory_soft_cap = Decimal("0.05")
        self.market = "market:2"  # Will be set by maker_engine
        
        LOG.info(
            "[trend] initialized: enabled=%s, lookback=%.1fs, down_threshold=%.1fbps",
            self.enabled,
            self.lookback_seconds,
            self.down_threshold_bps,
        )
    
    def set_inventory_soft_cap(self, soft_cap: Decimal):
        """Set inventory soft cap for inventory-aware trend decisions."""
        self.inventory_soft_cap = soft_cap
    
    def update(self, mid: float, timestamp: Optional[float] = None) -> None:
        """
        Update trend state with new mid price.
        
        Args:
            mid: Current mid price
            timestamp: Current timestamp (defaults to time.time())
        """
        if not self.enabled:
            return
        
        now = timestamp if timestamp is not None else time.time()
        self._samples.append((now, mid))
        
        # Remove old samples outside lookback window
        while self._samples and now - self._samples[0][0] > self.lookback_seconds:
            self._samples.popleft()
    
    def set_market(self, market: str):
        """Set market identifier for inventory lookups."""
        self.market = market
    
    def get_spread_adjustment_and_bias(
        self,
        current_mid: float,
    ) -> Tuple[str, float]:
        """
        Get spread adjustment and quote bias based on current trend.
        
        Returns:
            Tuple of (bias, extra_spread_bps):
            - bias: "both", "ask", or "bid"
            - extra_spread_bps: Additional spread in basis points
        """
        if not self.enabled:
            return "both", 0.0
        
        if len(self._samples) < 2:
            self._trend_state = "neutral"
            return "both", 0.0
        
        # Calculate price change over lookback window
        _, oldest_mid = self._samples[0]
        delta_bps = 0.0
        if oldest_mid:
            delta_bps = ((current_mid - oldest_mid) / max(oldest_mid, 1e-9)) * 10000.0
        
        # Update trend state with hysteresis
        previous_state = self._trend_state
        threshold = self.threshold_bps
        down_threshold = self.down_threshold_bps
        hysteresis = self.resume_threshold_bps
        
        # Hysteresis: harder to exit states than enter
        if self._trend_state == "ask_only":
            if delta_bps < hysteresis:
                self._trend_state = "neutral"
        elif self._trend_state == "bid_only":
            if delta_bps > -hysteresis:
                self._trend_state = "neutral"
        
        # Enter new states
        if self._trend_state == "neutral":
            now = time.time()
            if delta_bps >= threshold:
                self._trend_state = "ask_only"
                self._trend_signal = "up"
            elif delta_bps <= -down_threshold:
                self._trend_state = "bid_only" if self.down_bias == "bid" else "ask_only"
                self._trend_signal = "down"
                if self.down_cooldown_seconds > 0:
                    self._downtrend_cooldown_until = max(
                        self._downtrend_cooldown_until,
                        now + self.down_cooldown_seconds,
                    )
            else:
                self._trend_signal = "neutral"
        elif self._trend_state == "ask_only" and self._trend_signal == "down":
            if delta_bps > -hysteresis:
                self._trend_signal = "neutral"
        elif self._trend_state == "bid_only" and self._trend_signal == "up":
            if delta_bps < hysteresis:
                self._trend_signal = "neutral"
        
        if self._trend_state == "neutral":
            self._trend_signal = "neutral"
        
        # Log state changes
        if previous_state != self._trend_state:
            LOG.info(
                "[trend] state -> %s (delta=%.2fbps)",
                self._trend_state,
                delta_bps,
            )
        
        # Determine bias and spread adjustment
        now = time.time()
        cooldown_active = (
            self.down_cooldown_seconds > 0
            and now < self._downtrend_cooldown_until
        )
        
        # Get current inventory for inventory-aware decisions
        inventory = Decimal("0")
        if self.state and hasattr(self.state, "get_inventory"):
            try:
                inv_raw = self.state.get_inventory(self.market)
                if inv_raw is not None:
                    inventory = Decimal(str(inv_raw))
            except Exception:
                pass
        
        inventory_abs = abs(inventory)
        inv_limit = max(Decimal("1e-9"), self.inventory_soft_cap * Decimal(str(self.inventory_soft_cap_ratio)))
        
        bias = "both"
        extra_spread = 0.0
        
        if self._trend_state == "ask_only":
            # Uptrend: prefer selling, but allow buying if inventory is too negative
            if inventory_abs > inv_limit and inventory < 0:
                bias = "both"  # Allow buying to reduce short inventory
            else:
                bias = "ask"
                extra_spread = (
                    self.extra_spread_bps
                    if self._trend_signal != "down"
                    else self.down_extra_spread_bps
                )
        elif self._trend_state == "bid_only":
            # Downtrend: prefer buying, but allow selling if inventory is too positive
            if inventory_abs > inv_limit and inventory > 0:
                bias = "both"  # Allow selling to reduce long inventory
            else:
                bias = "bid"
                extra_spread = self.extra_spread_bps
        
        # During cooldown, enforce ask bias if configured
        if cooldown_active and bias != "both":
            if bias != "ask":
                bias = "ask"
            extra_spread = max(extra_spread, self.down_extra_spread_bps)
        
        # Update telemetry
        if self.telemetry:
            try:
                states = {"both": 0.0, "ask": 1.0, "bid": -1.0}
                self.telemetry.set_gauge(
                    "maker_trend_bias", states.get(bias, 0.0)
                )
                self.telemetry.set_gauge(
                    "maker_trend_down_guard",
                    1.0
                    if (self._trend_signal == "down" or cooldown_active)
                    and bias != "both"
                    else 0.0,
                )
                self.telemetry.set_gauge(
                    "maker_trend_down_cooldown_active", 1.0 if cooldown_active else 0.0
                )
            except Exception:
                pass
        
        return bias, extra_spread
    
    def is_cooldown_active(self) -> bool:
        """Check if downtrend cooldown is currently active."""
        if not self.enabled:
            return False
        if self.down_cooldown_seconds <= 0:
            return False
        return time.time() < self._downtrend_cooldown_until
    
    def get_state(self) -> Dict[str, Any]:
        """Get current trend state for debugging."""
        return {
            "enabled": self.enabled,
            "trend_state": self._trend_state,
            "trend_signal": self._trend_signal,
            "cooldown_active": self.is_cooldown_active(),
            "samples_count": len(self._samples),
        }

