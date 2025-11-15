"""
PnL Guard Feature Module

Extracted from maker_engine.py to allow independent enable/disable.
Provides reactive spread widening and size reduction when realized PnL falls below threshold.
"""

import logging
import time
from decimal import Decimal
from typing import Dict, Any, Optional

LOG = logging.getLogger("pnl_guard")


class PnLGuard:
    """
    Reactively adjusts spreads and sizes when PnL falls below threshold.
    
    Current implementation uses rolling window and consecutive triggers.
    Can be simplified to larger threshold, less reactive in future.
    """
    
    def __init__(self, config: Dict[str, Any], state: Any = None, telemetry: Any = None):
        """
        Initialize PnL guard.
        
        Args:
            config: PnL guard config section from config.yaml
            state: StateStore instance (for FIFO PnL tracking)
            telemetry: Telemetry instance (optional)
        """
        self.config = config
        self.state = state
        self.telemetry = telemetry
        self.enabled = config.get("enabled", False)
        
        if not self.enabled:
            return
        
        # Config parameters
        self.realized_floor_quote = Decimal(str(config.get("realized_floor_quote", -0.20)))
        self.trigger_consecutive = int(config.get("trigger_consecutive", 1))
        self.widen_bps = float(config.get("widen_bps", 6.0))
        self.size_multiplier = float(config.get("size_multiplier", 0.85))
        self.max_extra_bps = float(config.get("max_extra_bps", 10.0))
        self.min_size_multiplier = float(config.get("min_size_multiplier", 0.6))
        self.cooldown_seconds = float(config.get("cooldown_seconds", 120))
        self.check_interval_seconds = float(config.get("check_interval_seconds", 15))
        self.window_seconds = float(config.get("window_seconds", 300))
        
        # State
        self._active = False
        self._spread_extra = 0.0
        self._size_mult = 1.0
        self._expiry_ts = 0.0
        self._consecutive_triggers = 0
        self._last_check_ts = 0.0
        
        # For FIFO PnL tracking (if available from state)
        self.market = "market:2"  # Will be set by maker_engine
        
        LOG.info(
            "[pnl_guard] initialized: enabled=%s, floor=%.2f, widen=%.1fbps",
            self.enabled,
            float(self.realized_floor_quote),
            self.widen_bps,
        )
    
    def set_market(self, market: str):
        """Set market identifier for PnL tracking."""
        self.market = market
    
    def check_and_update(self, realized_pnl: Optional[Decimal] = None) -> None:
        """
        Check PnL and update guard state if needed.
        
        Args:
            realized_pnl: Current realized PnL (if None, fetches from state)
        """
        if not self.enabled:
            return
        
        now = time.time()
        
        # Throttle checks
        if now - self._last_check_ts < self.check_interval_seconds:
            return
        self._last_check_ts = now
        
        # Get realized PnL
        if realized_pnl is None:
            realized_pnl = self._get_realized_pnl()
        
        # Check if below threshold
        if realized_pnl < self.realized_floor_quote:
            self._consecutive_triggers += 1
            
            if self._consecutive_triggers >= self.trigger_consecutive:
                # Trigger guard
                if not self._active:
                    LOG.warning(
                        "[pnl_guard] triggered: realized_pnl=%.2f < floor=%.2f",
                        float(realized_pnl),
                        float(self.realized_floor_quote),
                    )
                    self._activate()
        else:
            # Reset consecutive triggers if above threshold
            if self._consecutive_triggers > 0:
                self._consecutive_triggers = 0
                LOG.info("[pnl_guard] realized_pnl above floor, resetting triggers")
        
        # Check expiry
        if self._active and now >= self._expiry_ts:
            LOG.info("[pnl_guard] cooldown expired, deactivating")
            self._deactivate()
    
    def _activate(self) -> None:
        """Activate PnL guard (widen spreads, reduce size)."""
        self._active = True
        self._spread_extra = min(self.widen_bps, self.max_extra_bps)
        self._size_mult = max(self.min_size_multiplier, self.size_multiplier)
        self._expiry_ts = time.time() + self.cooldown_seconds
        
        if self.telemetry:
            try:
                self.telemetry.set_gauge("maker_pnl_guard_active", 1.0)
            except Exception:
                pass
    
    def _deactivate(self) -> None:
        """Deactivate PnL guard (reset to normal)."""
        was_active = self._active
        self._active = False
        self._spread_extra = 0.0
        self._size_mult = 1.0
        self._consecutive_triggers = 0
        
        if was_active and self.telemetry:
            try:
                self.telemetry.set_gauge("maker_pnl_guard_active", 0.0)
            except Exception:
                pass
    
    def get_spread_adjustment_bps(self) -> float:
        """Get current spread adjustment in basis points."""
        if not self.enabled or not self._active:
            return 0.0
        return self._spread_extra
    
    def get_size_multiplier(self) -> float:
        """Get current size multiplier."""
        if not self.enabled or not self._active:
            return 1.0
        return self._size_mult
    
    def _get_realized_pnl(self) -> Decimal:
        """Get current FIFO realized PnL from state."""
        # Try to get from state if available
        if self.state and hasattr(self.state, "get_fifo_realized_pnl"):
            try:
                pnl = self.state.get_fifo_realized_pnl(self.market)
                if pnl is not None:
                    return Decimal(str(pnl))
            except Exception:
                pass
        
        # Fallback: return 0 (guard won't trigger)
        return Decimal("0")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current guard state for debugging."""
        return {
            "enabled": self.enabled,
            "active": self._active,
            "spread_extra_bps": self._spread_extra,
            "size_multiplier": self._size_mult,
            "consecutive_triggers": self._consecutive_triggers,
            "expiry_ts": self._expiry_ts,
            "realized_pnl": str(self._get_realized_pnl()),
        }

