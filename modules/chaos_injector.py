# modules/chaos_injector.py
"""
Chaos injector for M8: injects failures and stress conditions to test resilience.
- Latency spikes: delays in frame processing
- Reconnects: simulates WS disconnections
- Quote-width spikes: volatile market conditions
- Cancel-rate testing: triggers cancel discipline
"""
import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional

LOG = logging.getLogger("chaos")


class ChaosInjector:
    """
    Injects chaos into the system for testing resilience.

    Config options:
      enabled: bool - enable chaos injection
      latency:
        enabled: bool
        probability: float (0.0-1.0) - chance per frame
        min_ms: float - minimum latency to inject
        max_ms: float - maximum latency to inject
        spike_probability: float - chance of a large spike
        spike_multiplier: float - multiplier for spikes
      reconnect:
        enabled: bool
        probability: float - chance per second
        min_interval_s: float - minimum time between reconnects
        max_interval_s: float - maximum time between reconnects
      quote_width:
        enabled: bool
        probability: float - chance per quote
        min_bps: float - minimum additional spread
        max_bps: float - maximum additional spread
      cancel_rate:
        enabled: bool
        force_cancels_per_min: int - force this many cancels per minute
    """

    def __init__(self, config: Dict[str, Any]):
        self.cfg = config or {}
        chaos_cfg = self.cfg.get("chaos") or {}
        self.enabled = bool(chaos_cfg.get("enabled", False))

        if not self.enabled:
            return

        # Latency injection
        latency_cfg = chaos_cfg.get("latency") or {}
        self.latency_enabled = bool(latency_cfg.get("enabled", False))
        self.latency_prob = float(latency_cfg.get("probability", 0.1))
        self.latency_min_ms = float(latency_cfg.get("min_ms", 10.0))
        self.latency_max_ms = float(latency_cfg.get("max_ms", 100.0))
        self.latency_spike_prob = float(latency_cfg.get("spike_probability", 0.05))
        self.latency_spike_mult = float(latency_cfg.get("spike_multiplier", 10.0))

        # Reconnect simulation
        reconnect_cfg = chaos_cfg.get("reconnect") or {}
        self.reconnect_enabled = bool(reconnect_cfg.get("enabled", False))
        self.reconnect_prob = float(reconnect_cfg.get("probability", 0.01))
        self.reconnect_min_interval = float(
            reconnect_cfg.get("min_interval_s", 30.0)
        )
        self.reconnect_max_interval = float(
            reconnect_cfg.get("max_interval_s", 120.0)
        )
        self._last_reconnect = 0.0

        # Quote-width spikes
        quote_cfg = chaos_cfg.get("quote_width") or {}
        self.quote_enabled = bool(quote_cfg.get("enabled", False))
        self.quote_prob = float(quote_cfg.get("probability", 0.05))
        self.quote_min_bps = float(quote_cfg.get("min_bps", 20.0))
        self.quote_max_bps = float(quote_cfg.get("max_bps", 100.0))

        # Cancel-rate testing
        cancel_cfg = chaos_cfg.get("cancel_rate") or {}
        self.cancel_enabled = bool(cancel_cfg.get("enabled", False))
        self.cancel_rate_per_min = int(cancel_cfg.get("force_cancels_per_min", 60))
        self._cancel_timestamps: List[float] = []

        # State
        self._reconnect_callbacks: List[Callable[[], None]] = []
        self._quote_modifiers: List[Callable[[float], float]] = []

        LOG.info(
            "[chaos] injector initialized: latency=%s reconnect=%s quote=%s cancel=%s",
            self.latency_enabled,
            self.reconnect_enabled,
            self.quote_enabled,
            self.cancel_enabled,
        )

    # ----------------------- Latency Injection -----------------------

    async def inject_latency(self, frame_count: int = 1):
        """Inject latency spike if enabled and probability triggers."""
        if not self.enabled or not self.latency_enabled:
            return

        for _ in range(frame_count):
            if random.random() < self.latency_prob:
                # Check for spike
                is_spike = random.random() < self.latency_spike_prob
                if is_spike:
                    delay_ms = (
                        random.uniform(self.latency_min_ms, self.latency_max_ms)
                        * self.latency_spike_mult
                    )
                    LOG.warning(
                        "[chaos] injecting LATENCY SPIKE: %.1fms", delay_ms
                    )
                else:
                    delay_ms = random.uniform(
                        self.latency_min_ms, self.latency_max_ms
                    )
                    LOG.debug("[chaos] injecting latency: %.1fms", delay_ms)

                await asyncio.sleep(delay_ms / 1000.0)

    # ----------------------- Reconnect Simulation -----------------------

    def register_reconnect_callback(self, callback: Callable[[], None]):
        """Register a callback to trigger on simulated reconnects."""
        self._reconnect_callbacks.append(callback)

    async def check_reconnect(self):
        """Check if reconnect should be triggered."""
        if not self.enabled or not self.reconnect_enabled:
            return False

        now = time.time()
        if now - self._last_reconnect < self.reconnect_min_interval:
            return False

        if random.random() < self.reconnect_prob:
            self._last_reconnect = now
            LOG.warning(
                "[chaos] simulating WS RECONNECT (triggers callbacks)"
            )
            for cb in self._reconnect_callbacks:
                try:
                    cb()
                except Exception as e:
                    LOG.debug("[chaos] reconnect callback error: %s", e)
            return True

        return False

    # ----------------------- Quote-Width Spikes -----------------------

    def register_quote_modifier(self, modifier: Callable[[float], float]):
        """Register a function to modify quote spreads."""
        self._quote_modifiers.append(modifier)

    def modify_quote_spread(self, base_spread_bps: float) -> float:
        """Apply chaos to quote spread if enabled."""
        if not self.enabled or not self.quote_enabled:
            return base_spread_bps

        if random.random() < self.quote_prob:
            spike_bps = random.uniform(self.quote_min_bps, self.quote_max_bps)
            new_spread = base_spread_bps + spike_bps
            LOG.warning(
                "[chaos] QUOTE WIDTH SPIKE: %.2f bps -> %.2f bps (+%.2f)",
                base_spread_bps,
                new_spread,
                spike_bps,
            )
            return new_spread

        return base_spread_bps

    # ----------------------- Cancel-Rate Testing -----------------------

    def should_force_cancel(self) -> bool:
        """Return True if we should force a cancel to test cancel discipline."""
        if not self.enabled or not self.cancel_enabled:
            return False

        now = time.time()
        # Clean old timestamps (> 1 minute)
        cutoff = now - 60.0
        self._cancel_timestamps = [t for t in self._cancel_timestamps if t > cutoff]

        # Check if we need more cancels
        if len(self._cancel_timestamps) < self.cancel_rate_per_min:
            self._cancel_timestamps.append(now)
            LOG.warning(
                "[chaos] FORCE CANCEL (testing cancel discipline: %d/%d per min)",
                len(self._cancel_timestamps),
                self.cancel_rate_per_min,
            )
            return True

        return False

    def get_cancel_rate(self) -> int:
        """Return current cancel rate (cancels per minute)."""
        now = time.time()
        cutoff = now - 60.0
        self._cancel_timestamps = [t for t in self._cancel_timestamps if t > cutoff]
        return len(self._cancel_timestamps)

    # ----------------------- Async Task -----------------------

    async def run(self):
        """Run background chaos tasks."""
        if not self.enabled:
            return

        LOG.info("[chaos] starting background chaos tasks")
        while True:
            try:
                await self.check_reconnect()
                await asyncio.sleep(1.0)  # Check every second
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOG.debug("[chaos] background task error: %s", e)
                await asyncio.sleep(1.0)

