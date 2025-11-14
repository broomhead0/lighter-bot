# modules/maker_engine.py
import asyncio
import logging
import math
import random
import time
from collections import deque
from decimal import Decimal
from typing import Any, Deque, Dict, Optional, Tuple

from core.trading_client import TradingClient, TradingConfig

LOG = logging.getLogger("maker")


class MakerEngine:
    """
    Minimal maker engine compatible with your M3–M6 flow.

    - Pulls current mid from StateStore (if present) for a target market.
    - Emits periodic "quotes" (dry-run by default) around the mid with a configurable spread.
    - M7: touches telemetry heartbeat 'quote' whenever it refreshes quotes so watchdogs can alert.

    If your M5+ REST v1 exists, you can wire actual post-only orders in `_post_quotes()`.
    This implementation keeps dry-run behavior so it's safe to run without keys.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        state: Any = None,
        alert_manager: Any = None,  # M7 optional
        telemetry: Any = None,  # M7 optional
        chaos_injector: Any = None,  # M8 optional
        guard: Any = None,  # SelfTradeGuard
        trading_client: Optional[TradingClient] = None,
    ):
        self.cfg = config or {}
        self.state = state
        self.alerts = alert_manager
        self.telemetry = telemetry
        self.chaos = chaos_injector
        self.guard = guard

        maker_cfg = (
            (self.cfg.get("maker") or {})
            if isinstance(self.cfg.get("maker"), dict)
            else {}
        )
        self.market = maker_cfg.get("pair", "market:1")
        self.base_size = float(maker_cfg.get("size", 0.001))
        self.min_size = float(maker_cfg.get("size_min", self.base_size * 0.7))
        self.max_size = float(maker_cfg.get("size_max", self.base_size * 1.3))
        if self.min_size > self.max_size:
            self.min_size, self.max_size = self.max_size, self.min_size
        self.exchange_min_size = float(maker_cfg.get("exchange_min_size", 0.001))
        try:
            self.size_scale = int(float(maker_cfg.get("size_scale", 1)))
        except Exception:
            self.size_scale = 1
        if self.size_scale <= 0:
            self.size_scale = 1
        self.exchange_min_notional = float(
            maker_cfg.get("exchange_min_notional", 0.0)
        )
        self.min_size = max(self.min_size, self.exchange_min_size)
        self.inventory_soft_cap = float(
            maker_cfg.get("inventory_soft_cap", self.base_size * 100)
        )
        self.spread_bps = float(maker_cfg.get("spread_bps", 10.0))  # 10 bps default
        self.refresh_seconds = float(maker_cfg.get("refresh_seconds", 5.0))
        self.randomize_bps = float(
            maker_cfg.get("randomize_bps", 4.0)
        )  # random widen/narrow
        self.allow_synthetic_fallback = bool(maker_cfg.get("synthetic_fallback", False))

        pnl_guard_cfg = maker_cfg.get("pnl_guard") or {}
        self.pnl_guard_enabled = bool(pnl_guard_cfg.get("enabled", False))
        self.pnl_guard_max_extra_bps = float(pnl_guard_cfg.get("max_extra_bps", 6.0))
        self.pnl_guard_min_size_multiplier = float(
            pnl_guard_cfg.get("min_size_multiplier", 0.6)
        )
        self._pnl_guard_spread_extra = 0.0
        self._pnl_guard_size_multiplier = 1.0
        self._pnl_guard_expiry_ts = 0.0

        vol_cfg = maker_cfg.get("volatility") or {}
        self.vol_enabled = bool(vol_cfg.get("enabled", False))
        self.vol_low_bps = float(vol_cfg.get("low_bps", 5.0))
        self.vol_high_bps = float(vol_cfg.get("high_bps", 25.0))
        self.vol_min_spread = float(vol_cfg.get("min_spread_bps", self.spread_bps))
        self.vol_max_spread = float(
            vol_cfg.get("max_spread_bps", max(self.spread_bps, self.spread_bps * 2))
        )
        self.vol_min_size_multiplier = float(vol_cfg.get("min_size_multiplier", 0.5))
        self.vol_max_size_multiplier = float(vol_cfg.get("max_size_multiplier", 1.0))
        if self.vol_min_size_multiplier > self.vol_max_size_multiplier:
            self.vol_min_size_multiplier, self.vol_max_size_multiplier = (
                self.vol_max_size_multiplier,
                self.vol_min_size_multiplier,
            )
        self.vol_pause_threshold = float(vol_cfg.get("pause_threshold_bps", 35.0))
        self.vol_resume_threshold = float(vol_cfg.get("resume_threshold_bps", 25.0))
        self.vol_resume_inventory_ratio = float(
            vol_cfg.get("resume_inventory_ratio", 0.25)
        )
        self.vol_high_vol_threshold = float(
            vol_cfg.get("high_vol_threshold_bps", 0.0)
        )
        self.vol_high_vol_size_multiplier = float(
            vol_cfg.get("high_vol_size_multiplier", 1.0)
        )
        # Low volatility pause: pause maker when volatility is too low to avoid bleeding on hedging
        self.vol_low_vol_pause_threshold = float(
            vol_cfg.get("low_vol_pause_threshold_bps", 3.0)
        )
        self.vol_low_vol_resume_threshold = float(
            vol_cfg.get("low_vol_resume_threshold_bps", 4.5)
        )
        self.vol_half_life = max(float(vol_cfg.get("ema_halflife_seconds", 30.0)), 1.0)
        self._volatility_ema: Optional[float] = None
        self._volatility_last_mid: Optional[float] = None
        self._volatility_last_ts: float = time.time()
        self._volatility_paused = False
        self._low_volatility_paused = False
        self._latest_volatility_bps: float = 0.0
        self._volatility_paused_since: Optional[float] = None
        self._low_volatility_paused_since: Optional[float] = None

        trend_cfg = maker_cfg.get("trend") or {}
        self.trend_enabled = bool(trend_cfg.get("enabled", False))
        self.trend_lookback = float(trend_cfg.get("lookback_seconds", 30.0))
        self.trend_threshold_bps = float(trend_cfg.get("threshold_bps", 15.0))
        self.trend_down_threshold_bps = float(
            trend_cfg.get("down_threshold_bps", self.trend_threshold_bps)
        )
        self.trend_hysteresis_bps = float(trend_cfg.get("resume_threshold_bps", 8.0))
        self.trend_extra_spread_bps = float(trend_cfg.get("extra_spread_bps", 3.0))
        self.trend_down_extra_spread_bps = float(
            trend_cfg.get("down_extra_spread_bps", self.trend_extra_spread_bps)
        )
        down_bias_cfg = str(trend_cfg.get("down_bias", "bid")).lower()
        self.trend_down_state = (
            "ask_only" if down_bias_cfg.startswith("ask") else "bid_only"
        )
        self.trend_down_cooldown_seconds = float(
            trend_cfg.get("down_cooldown_seconds", 45.0)
        )
        self._base_trend_down_cooldown = self.trend_down_cooldown_seconds
        self.trend_inventory_ratio = float(
            trend_cfg.get("inventory_soft_cap_ratio", 0.7)
        )
        self._trend_samples: Deque[Tuple[float, float]] = deque(maxlen=256)
        self._trend_state: str = "neutral"
        self._downtrend_cooldown_until: float = 0.0
        self._trend_signal: str = "neutral"
        regimes_cfg = maker_cfg.get("regimes") or {}
        aggressive_cfg = regimes_cfg.get("aggressive") or {}
        defensive_cfg = regimes_cfg.get("defensive") or {}

        def _profile(cfg, default_size, default_spread, default_cooldown):
            return {
                "size_multiplier": float(cfg.get("size_multiplier", default_size)),
                "extra_spread_bps": float(cfg.get("extra_spread_bps", default_spread)),
                "down_cooldown_seconds": float(
                    cfg.get("down_cooldown_seconds", default_cooldown)
                ),
            }

        self._regime_profiles = {
            "aggressive": _profile(
                aggressive_cfg,
                1.0,
                0.0,
                max(0.0, self._base_trend_down_cooldown * 0.4),
            ),
            "defensive": _profile(
                defensive_cfg,
                0.7,
                2.0,
                self._base_trend_down_cooldown if self._base_trend_down_cooldown else 45.0,
            ),
        }
        self._regime_min_dwell = float(regimes_cfg.get("min_dwell_seconds", 60.0))
        self._regime_vol_threshold_bps = float(regimes_cfg.get("vol_threshold_bps", 8.0))
        self._current_regime: str = "defensive"
        self._regime_last_switch: float = time.time()
        self._regime_size_multiplier: float = 1.0
        self._regime_spread_bonus: float = 0.0
        self._apply_regime(self._current_regime, initial=True)
        self._pnl_guard_active_flag: bool = False

        # Cancel discipline tracking
        limits_cfg = maker_cfg.get("limits") or {}
        self.max_cancels = int(limits_cfg.get("max_cancels", 30))
        self._cancel_count_this_minute = 0
        self._cancel_window_start = time.time()
        self._is_throttled = False

        # Order tracking
        self._open_orders: Dict[str, Dict[str, Any]] = {}  # order_id -> order info

        # Trading client (Signer-based) for live order placement
        self._trading_client: Optional[TradingClient] = trading_client
        self._owns_trading_client = False
        if self._trading_client is None:
            api_cfg = self.cfg.get("api") or {}
            trading_cfg = self._build_trading_config(api_cfg)
            if trading_cfg:
                try:
                    self._trading_client = TradingClient(trading_cfg)
                    self._owns_trading_client = True
                    LOG.info("[maker] trading client ready for live orders")
                except Exception as exc:
                    LOG.warning("[maker] trading client unavailable: %s", exc)

        self._stop = asyncio.Event()
        if self.telemetry and self.pnl_guard_enabled:
            try:
                self.telemetry.set_gauge("maker_pnl_guard_active", 0.0)
            except Exception:
                pass

    async def run(self):
        LOG.info("MakerEngine started for %s", self.market)
        try:
            while not self._stop.is_set():
                mid = await self._get_mid()
                if mid is None:
                    LOG.info("[maker] waiting for mid...")
                    await asyncio.sleep(1.0)
                    continue

                self._maybe_expire_pnl_guard()

                volatility_bps = self._update_volatility(mid)
                self._latest_volatility_bps = volatility_bps

                if self.vol_enabled and (self._volatility_paused or self._low_volatility_paused):
                    pause_reason = (
                        "high volatility/inventory"
                        if self._volatility_paused
                        else "low volatility (hedging costs too high)"
                    )
                    LOG.debug(
                        "[maker] skipping quotes due to %s (%.2fbps)",
                        pause_reason,
                        volatility_bps,
                    )
                    await self._cancel_all_orders()
                    self._touch_quote()
                    await asyncio.sleep(self.refresh_seconds)
                    continue

                trend_bias, extra_spread = self._update_trend_state(mid)

                # Phase 2: Get inventory for spread widening and size reduction
                inventory = Decimal("0")
                inventory_abs = Decimal("0")
                if self.state and hasattr(self.state, "get_inventory"):
                    try:
                        inv_raw = self.state.get_inventory(self.market)
                        if inv_raw is not None:
                            inventory = Decimal(str(inv_raw))
                            inventory_abs = abs(inventory)
                    except Exception:
                        pass

                # Phase 2: Inventory-based spread widening
                # Wider spreads as inventory builds to make fills less attractive
                inventory_spread_bps = 0.0
                if inventory_abs > Decimal("0.03"):
                    inventory_spread_bps = 6.0
                elif inventory_abs > Decimal("0.02"):
                    inventory_spread_bps = 4.0
                elif inventory_abs > Decimal("0.01"):
                    inventory_spread_bps = 2.0

                bid, ask, spread = self._compute_quotes(
                    mid, volatility_bps, extra_spread_bps=extra_spread + inventory_spread_bps
                )

                # Phase 2: Inventory-based size reduction
                # Reduce size when inventory exists to prevent adding to position
                inventory_size_multiplier = 1.0
                if inventory_abs > Decimal("0.02"):
                    inventory_size_multiplier = 0.50
                elif inventory_abs > Decimal("0.01"):
                    inventory_size_multiplier = 0.75

                # Compute base quote size (includes PnL guard multiplier inside)
                quote_size = self._compute_quote_size(mid, volatility_bps)

                # Apply inventory size multiplier (after PnL guard but before final quantization)
                quote_size *= inventory_size_multiplier

                # CRITICAL: Ensure size meets BOTH exchange minimum size AND notional after ALL multipliers
                # This can happen when: base_size (0.064) * pnl_guard (0.85) * inventory (0.75) = 0.0408
                original_size = quote_size

                # First ensure minimum size
                if quote_size < self.exchange_min_size:
                    quote_size = self.exchange_min_size

                # Then ensure minimum notional (price * size must be >= min_notional)
                if mid and self.exchange_min_notional > 0:
                    min_size_for_notional = self.exchange_min_notional / mid
                    if quote_size < min_size_for_notional:
                        # Round up to nearest lot step to meet notional
                        scale = max(1, self.size_scale)
                        raw_units = min_size_for_notional
                        quantized = math.ceil(raw_units * scale) / float(scale)
                        quote_size = max(quote_size, quantized)
                        LOG.debug(
                            "[maker] size quantization: adjusted from %.6f to %.6f (notional: %.2f @ %.2f = $%.2f)",
                            original_size,
                            quote_size,
                            quote_size,
                            mid,
                            quote_size * mid
                        )

                # Check cancel discipline (throttle if exceeded)
                self._check_cancel_discipline()

                # Guard: validate quotes before posting
                guard_blocked = False
                if self.guard:
                    if not self.guard.is_allowed(
                        Decimal(str(mid)),
                        Decimal(str(bid)),
                        Decimal(str(ask)),
                        self.market
                    ):
                        guard_blocked = True
                        LOG.warning(
                            "[maker] quote blocked by guard: mid=%.4f bid=%.4f ask=%.4f",
                            mid,
                            bid,
                            ask,
                        )
                        if self.state and hasattr(self.state, "mark_guard_blocked"):
                            try:
                                self.state.mark_guard_blocked(self.market, time.time())
                            except Exception:
                                pass
                        if self.telemetry:
                            try:
                                self.telemetry.set_gauge("maker_guard_block_active", 1.0)
                            except Exception:
                                pass
                        await self._cancel_all_orders()
                        await asyncio.sleep(self.refresh_seconds)
                        continue
                if not guard_blocked and self.state and hasattr(self.state, "clear_guard_block"):
                    try:
                        self.state.clear_guard_block(self.market)
                    except Exception:
                        pass
                if self.telemetry:
                    try:
                        self.telemetry.set_gauge("maker_guard_block_active", 0.0)
                    except Exception:
                        pass

                # Chaos: force cancel if testing cancel discipline
                if self.chaos and self.chaos.should_force_cancel():
                    LOG.warning(
                        "[maker] CHAOS: forcing cancel (testing cancel discipline)"
                    )
                    self._record_cancel()

                if quote_size < self.exchange_min_size:
                    LOG.info(
                        "[maker] skipping quote refresh (size %.6f below exchange min %.6f)",
                        quote_size,
                        self.exchange_min_size,
                    )
                    await asyncio.sleep(self.refresh_seconds)
                    continue

                place_bid = trend_bias in ("both", "bid")
                place_ask = trend_bias in ("both", "ask")

                # Phase 2: Asymmetric quoting based on inventory
                # If inventory exists, stop quoting the side that adds to position
                # Work WITH hedger instead of against it
                asymmetric_threshold = Decimal("0.01")  # 0.01 SOL threshold

                if inventory_abs > asymmetric_threshold:
                    if inventory > 0:  # Long inventory
                        # Stop placing bids (don't add to long position)
                        # Keep asking to flatten inventory
                        if place_bid:
                            LOG.info(
                                "[maker] asymmetric quoting: disabling bids (long inventory %.4f)",
                                float(inventory)
                            )
                        place_bid = False
                    else:  # Short inventory
                        # Stop placing asks (don't add to short position)
                        # Keep bidding to flatten inventory
                        if place_ask:
                            LOG.info(
                                "[maker] asymmetric quoting: disabling asks (short inventory %.4f)",
                                float(inventory)
                            )
                        place_ask = False

                if not place_bid and not place_ask:
                    LOG.debug("[maker] trend/inventory filter skipping both sides")
                    await self._cancel_all_orders()
                    await asyncio.sleep(self.refresh_seconds)
                    continue

                await self._post_quotes(
                    bid,
                    ask,
                    quote_size,
                    place_bid=place_bid,
                    place_ask=place_ask,
                )

                # touch heartbeat for M7 watchdogs
                self._touch_quote()

                LOG.info(
                    "[market:%s] mid=%.4f | bid=%.4f | ask=%.4f | spread=%.2fbps",
                    self.market,
                    mid,
                    bid,
                    ask,
                    spread,
                )
                await asyncio.sleep(self.refresh_seconds)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._alert("error", "Maker crashed", str(e))
            raise

    async def stop(self):
        self._stop.set()
        if self._owns_trading_client and self._trading_client:
            try:
                await self._trading_client.close()
            except Exception as exc:
                LOG.debug("[maker] trading client close failed: %s", exc)

    # ----------------------- Helpers --------------------------

    async def _get_mid(self) -> Optional[float]:
        # Preferred: pull from StateStore if provided
        try:
            if self.state and hasattr(self.state, "get_mid"):
                m = self.state.get_mid(self.market)
                if m is not None:
                    return float(m)
        except Exception:
            pass
        if self.allow_synthetic_fallback:
            return self._synthetic_mid()
        return None

    def _compute_quotes(
        self,
        mid: float,
        volatility_bps: Optional[float] = None,
        *,
        extra_spread_bps: float = 0.0,
    ) -> Tuple[float, float, float]:
        base_spread = self._spread_for_volatility(volatility_bps) + max(
            0.0, extra_spread_bps
        )
        if self._regime_spread_bonus > 0.0:
            base_spread += self._regime_spread_bonus
        if self.pnl_guard_enabled:
            base_spread += max(0.0, self._pnl_guard_spread_extra)
        jitter = random.uniform(-self.randomize_bps, self.randomize_bps)
        bps = max(1e-6, base_spread + jitter)

        # Apply chaos quote-width spikes if enabled
        if self.chaos:
            bps = self.chaos.modify_quote_spread(bps)

        half = (bps / 20000.0) * mid  # half-spread in price units
        bid = max(0.0000001, mid - half)
        ask = mid + half
        return bid, ask, bps

    async def _post_quotes(
        self,
        bid: float,
        ask: float,
        size: float,
        *,
        place_bid: bool = True,
        place_ask: bool = True,
    ):
        """
        Post maker quotes (bid/ask) as post-only limit orders.
        - Cancel existing orders first
        - Place new bid and ask orders
        - Track orders for cancellation on next refresh
        """
        # Cancel existing orders if throttled
        if self._is_throttled:
            LOG.warning("[maker] throttled due to cancel limit, skipping quote refresh")
            return

        # Cancel existing orders
        await self._cancel_all_orders()

        # Place new orders if REST client available
        if self._trading_client and not self.cfg.get("maker", {}).get("dry_run", True):
            try:
                if place_bid:
                    await self._place_order("bid", bid, size)
                if place_ask:
                    await self._place_order("ask", ask, size)
            except Exception as e:
                LOG.error(f"[maker] failed to place orders: {e}")
                await self._alert("error", "Order placement failed", str(e))
        else:
            # Dry-run mode: just log
            LOG.debug(
                "[maker] DRY-RUN: would place bid=%s ask=%s size=%.6f",
                f"{bid:.4f}" if place_bid else "skipped",
                f"{ask:.4f}" if place_ask else "skipped",
                size,
            )

    def _touch_quote(self):
        if getattr(self, "telemetry", None):
            try:
                self.telemetry.touch("quote")
            except Exception:
                pass

    def _compute_quote_size(
        self,
        mid: Optional[float],
        volatility_bps: Optional[float] = None,
    ) -> float:
        size = self.base_size * self._regime_size_multiplier
        min_size = max(1e-6, self.min_size)
        max_size = max(min_size, self.max_size)
        inv_soft_cap = max(1e-9, self.inventory_soft_cap)

        if self.state and hasattr(self.state, "get_inventory"):
            try:
                inv = self.state.get_inventory(self.market)
                if inv is not None:
                    inv_float = abs(float(inv))
                    ratio = min(1.0, inv_float / inv_soft_cap)
                    size = max_size - (max_size - min_size) * ratio
            except Exception:
                size = self.base_size

        high_vol_clip = False
        if self.vol_enabled and volatility_bps is not None:
            factor = self._volatility_factor(volatility_bps)
            multiplier_span = self.vol_max_size_multiplier - self.vol_min_size_multiplier
            multiplier = self.vol_max_size_multiplier - multiplier_span * factor
            size *= max(0.0, multiplier)
            if (
                self.vol_high_vol_threshold > 0.0
                and self.vol_high_vol_size_multiplier > 0.0
                and volatility_bps >= self.vol_high_vol_threshold
            ):
                size *= self.vol_high_vol_size_multiplier
                high_vol_clip = True

        size = min(max_size, max(min_size, size))
        if size < self.exchange_min_size:
            size = self.exchange_min_size
        if self.pnl_guard_enabled:
            guard_multiplier = max(
                self.pnl_guard_min_size_multiplier,
                min(1.0, self._pnl_guard_size_multiplier),
            )
            size *= guard_multiplier
            size = min(max_size, max(min_size, size))
            if size < self.exchange_min_size:
                size = self.exchange_min_size
        effective_mid = mid
        if effective_mid is None and self.state and hasattr(self.state, "get_mid"):
            try:
                mid_val = self.state.get_mid(self.market)
                if mid_val:
                    effective_mid = float(mid_val)
            except Exception:
                effective_mid = None
        min_units = self._min_units_for_notional(effective_mid)
        if min_units is not None and size < min_units:
            size = min_units
            size = min(max_size, max(min_size, size))
            if size < self.exchange_min_size:
                size = self.exchange_min_size
        if getattr(self, "telemetry", None):
            try:
                self.telemetry.set_gauge("maker_quote_size", float(size))
                if self.vol_enabled and self.vol_high_vol_threshold > 0.0:
                    self.telemetry.set_gauge(
                        "maker_high_vol_clip_active", 1.0 if high_vol_clip else 0.0
                    )
            except Exception:
                pass
        return float(size)

    def _min_units_for_notional(self, mid: Optional[float]) -> Optional[float]:
        if self.exchange_min_notional <= 0.0 or mid is None or mid <= 0.0:
            if self.exchange_min_size > 0.0:
                return max(self.exchange_min_size, self.min_size)
            return None
        scale = max(1, self.size_scale)
        raw_units = self.exchange_min_notional / mid
        quantized = math.ceil(raw_units * scale) / float(scale)
        return max(self.exchange_min_size, quantized)

    def _current_inventory(self) -> float:
        if self.state and hasattr(self.state, "get_inventory"):
            try:
                inv = self.state.get_inventory(self.market)
                if inv is not None:
                    return float(inv)
            except Exception:
                return 0.0
        return 0.0

    def _can_resume_from_pause(self) -> bool:
        inv_limit = max(1e-9, self.inventory_soft_cap * self.vol_resume_inventory_ratio)
        current_inv = abs(self._current_inventory())
        return current_inv <= inv_limit

    def _update_trend_state(self, mid: float) -> Tuple[str, float]:
        if not self.trend_enabled:
            return "both", 0.0

        now = time.time()
        self._trend_samples.append((now, mid))
        while self._trend_samples and now - self._trend_samples[0][0] > self.trend_lookback:
            self._trend_samples.popleft()

        if len(self._trend_samples) < 2:
            self._trend_state = "neutral"
            return "both", 0.0

        _, oldest_mid = self._trend_samples[0]
        delta_bps = 0.0
        if oldest_mid:
            delta_bps = ((mid - oldest_mid) / max(oldest_mid, 1e-9)) * 10000.0

        previous_state = self._trend_state
        threshold = self.trend_threshold_bps
        down_threshold = self.trend_down_threshold_bps
        hysteresis = self.trend_hysteresis_bps

        if self._trend_state == "ask_only":
            if delta_bps < hysteresis:
                self._trend_state = "neutral"
        elif self._trend_state == "bid_only":
            if delta_bps > -hysteresis:
                self._trend_state = "neutral"

        if self._trend_state == "neutral":
            if delta_bps >= threshold:
                self._trend_state = "ask_only"
                self._trend_signal = "up"
            elif delta_bps <= -down_threshold:
                self._trend_state = self.trend_down_state
                self._trend_signal = "down"
                if self.trend_down_cooldown_seconds > 0:
                    self._downtrend_cooldown_until = max(
                        self._downtrend_cooldown_until,
                        now + self.trend_down_cooldown_seconds,
                    )
            else:
                self._trend_signal = "neutral"
        elif self._trend_state == "ask_only" and self._trend_signal == "down":
            if delta_bps > -hysteresis:
                self._trend_signal = "neutral"
        elif self._trend_state == "bid_only" and self._trend_signal == "up":
            if delta_bps < hysteresis:
                self._trend_signal = "neutral"

        if previous_state != self._trend_state:
            LOG.info(
                "[maker] trend state -> %s (delta=%.2fbps)",
                self._trend_state,
                delta_bps,
            )
        if self._trend_state == "neutral":
            self._trend_signal = "neutral"

        current_inv = self._current_inventory()
        inv_abs = abs(current_inv)
        inv_limit = max(1e-9, self.inventory_soft_cap * self.trend_inventory_ratio)
        bias = "both"
        extra_spread = 0.0

        cooldown_active = (
            self.trend_down_cooldown_seconds > 0
            and now < self._downtrend_cooldown_until
        )

        self._maybe_update_regime(now, cooldown_active)

        if self._trend_state == "ask_only":
            if inv_abs > inv_limit and current_inv < 0:
                bias = "both"
            else:
                bias = "ask"
                extra_spread = (
                    self.trend_extra_spread_bps
                    if self._trend_signal != "down"
                    else self.trend_down_extra_spread_bps
                )
        elif self._trend_state == "bid_only":
            if inv_abs > inv_limit and current_inv > 0:
                bias = "both"
            else:
                bias = "bid"
                extra_spread = self.trend_extra_spread_bps

        if cooldown_active and bias != "both":
            if bias != "ask":
                bias = "ask"
            extra_spread = max(extra_spread, self.trend_down_extra_spread_bps)

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

    def _maybe_update_regime(self, now: float, cooldown_active: bool) -> None:
        # Regime switching priority:
        # 1. PnL guard active → defensive (highest priority)
        # 2. Downtrend cooldown or trend signal down → defensive
        # 3. Low volatility (< threshold) → defensive (overnight, need careful hedging)
        # 4. Otherwise → aggressive (high volatility, better liquidity)
        vol_bps = self._latest_volatility_bps or 0.0
        low_vol = vol_bps < self._regime_vol_threshold_bps

        target = (
            "defensive"
            if (
                self._pnl_guard_active_flag
                or cooldown_active
                or self._trend_signal == "down"
                or low_vol
            )
            else "aggressive"
        )
        if (
            target != self._current_regime
            and (now - self._regime_last_switch) >= self._regime_min_dwell
        ):
            self._apply_regime(target)

    def _apply_regime(self, name: str, initial: bool = False) -> None:
        profile = self._regime_profiles.get(name)
        if not profile:
            return
        self._current_regime = name
        self._regime_size_multiplier = max(0.1, profile.get("size_multiplier", 1.0))
        self._regime_spread_bonus = max(0.0, profile.get("extra_spread_bps", 0.0))
        cooldown = profile.get("down_cooldown_seconds", self._base_trend_down_cooldown)
        self.trend_down_cooldown_seconds = max(0.0, float(cooldown))
        self._regime_last_switch = time.time()
        if self.telemetry:
            try:
                self.telemetry.set_gauge(
                    "maker_regime_state", 1.0 if name == "aggressive" else 0.0
                )
            except Exception:
                pass
        if not initial:
            LOG.info(
                "[maker] regime -> %s (size x%.2f, spread +%.2fbps, cooldown %.0fs)",
                name,
                self._regime_size_multiplier,
                self._regime_spread_bonus,
                self.trend_down_cooldown_seconds,
            )

    async def _alert(self, level: str, title: str, message: str = ""):
        if getattr(self, "alerts", None) and hasattr(self.alerts, level):
            try:
                await getattr(self.alerts, level)(title, message)
            except Exception:
                pass

    # local synthetic mid (very cheap wander) for when WS hasn't filled state yet
    _syn_mid_anchor = time.time()

    def _synthetic_mid(self) -> float:
        t = time.time() - self._syn_mid_anchor
        base = 107000.0
        wave = 100.0 * math.sin(t / 9.0)
        noise = random.uniform(-20.0, 20.0)
        return max(1.0, base + wave + noise)

    def _check_cancel_discipline(self):
        """Check if cancel limit exceeded and throttle if needed."""
        now = time.time()
        # Reset counter every minute
        if now - self._cancel_window_start >= 60.0:
            self._cancel_count_this_minute = 0
            self._cancel_window_start = now
            self._is_throttled = False

        # Check if limit exceeded
        if self._cancel_count_this_minute >= self.max_cancels:
            if not self._is_throttled:
                LOG.warning(
                    f"[maker] cancel limit exceeded ({self._cancel_count_this_minute}/{self.max_cancels}), throttling"
                )
                self._is_throttled = True
                # Fire and forget alert (non-blocking)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self._alert("warning", "Cancel limit exceeded",
                            f"{self._cancel_count_this_minute}/{self.max_cancels} cancels this minute"))
                except Exception:
                    pass

    def _record_cancel(self):
        """Record a cancel operation."""
        self._cancel_count_this_minute += 1

    async def _cancel_all_orders(self):
        """Cancel all open orders."""
        if not self._open_orders:
            return

        cancel_count = len(self._open_orders)
        if self._trading_client and not self.cfg.get("maker", {}).get("dry_run", True):
            try:
                for order_id, order_info in list(self._open_orders.items()):
                    await self._cancel_order(order_id)
            except Exception as e:
                LOG.error(f"[maker] failed to cancel orders: {e}")
        else:
            # Dry-run: just clear tracking
            LOG.debug(f"[maker] DRY-RUN: would cancel {cancel_count} orders")

        self._open_orders.clear()
        if cancel_count > 0:
            self._record_cancel()

    async def _place_order(self, side: str, price: float, size: float) -> Optional[str]:
        """Place a post-only limit order. Returns order_id if successful."""
        if not self._trading_client:
            return None

        await self._trading_client.ensure_ready()
        order = await self._trading_client.create_post_only_limit(
            market=self.market,
            side=side,
            price=price,
            size=size,
        )

        order_id = str(order.client_order_index)

        self._open_orders[order_id] = {
            "side": side,
            "price": price,
            "size": size,
            "market": self.market,
            "timestamp": time.time(),
        }

        LOG.info(
            "[maker] submitted %s order id=%s size=%.6f price=%.4f tx=%s",
            side,
            order_id,
            size,
            price,
            order.tx_hash,
        )
        return order_id

    async def _cancel_order(self, order_id: str):
        """Cancel a specific order."""
        if not self._trading_client:
            return

        await self._trading_client.ensure_ready()
        await self._trading_client.cancel_order(
            market=self.market,
            client_order_index=int(order_id),
        )

        if order_id in self._open_orders:
            del self._open_orders[order_id]
        LOG.info("[maker] cancelled order %s", order_id)

    def _build_trading_config(self, api_cfg: Dict[str, Any]) -> Optional[TradingConfig]:
        base_url = api_cfg.get("base_url")
        private_key = api_cfg.get("private_key") or api_cfg.get("key")
        account_index = api_cfg.get("account_index")
        api_key_index = api_cfg.get("api_key_index")

        if not (base_url and private_key is not None and account_index is not None and api_key_index is not None):
            return None

        maker_cfg = self.cfg.get("maker") or {}
        base_scale = Decimal(str(maker_cfg.get("size_scale", 1)))
        price_scale = Decimal(str(maker_cfg.get("price_scale", 1)))

        try:
            return TradingConfig(
                base_url=str(base_url),
                api_key_private_key=str(private_key),
                account_index=int(account_index),
                api_key_index=int(api_key_index),
                base_scale=base_scale,
                price_scale=price_scale,
                max_api_key_index=(
                    int(api_cfg["max_api_key_index"]) if api_cfg.get("max_api_key_index") is not None else None
                ),
                nonce_management=api_cfg.get("nonce_management"),
            )
        except Exception as exc:
            LOG.warning("[maker] invalid trading config: %s", exc)
            return None

    def _maybe_expire_pnl_guard(self) -> None:
        if not self.pnl_guard_enabled:
            return
        if self._pnl_guard_expiry_ts and time.time() > self._pnl_guard_expiry_ts:
            if self._pnl_guard_spread_extra > 0 or self._pnl_guard_size_multiplier < 0.999:
                LOG.info("[maker] PnL guard expired; restoring baseline sizes/spread")
            self._pnl_guard_spread_extra = 0.0
            self._pnl_guard_size_multiplier = 1.0
            self._pnl_guard_expiry_ts = 0.0
            self._pnl_guard_active_flag = False
            self._set_pnl_guard_flag(False)
            if self.telemetry:
                try:
                    self.telemetry.set_gauge("maker_pnl_guard_active", 0.0)
                except Exception:
                    pass

    def apply_pnl_guard(
        self,
        extra_spread_bps: float,
        size_multiplier: float,
        ttl_seconds: float,
    ) -> None:
        if not self.pnl_guard_enabled:
            return
        ttl = max(0.0, float(ttl_seconds))
        self._pnl_guard_spread_extra = min(
            max(0.0, float(extra_spread_bps)), self.pnl_guard_max_extra_bps
        )
        self._pnl_guard_size_multiplier = max(
            self.pnl_guard_min_size_multiplier, min(1.0, float(size_multiplier))
        )
        self._pnl_guard_expiry_ts = time.time() + ttl if ttl > 0 else 0.0
        self._pnl_guard_active_flag = True
        self._set_pnl_guard_flag(True)
        LOG.warning(
            "[maker] PnL guard engaged: +%.2fbps spread, size x%.2f for %.0fs",
            self._pnl_guard_spread_extra,
            self._pnl_guard_size_multiplier,
            ttl,
        )
        if self.telemetry:
            try:
                self.telemetry.set_gauge("maker_pnl_guard_active", 1.0)
            except Exception:
                pass

    def clear_pnl_guard(self) -> None:
        if not self.pnl_guard_enabled:
            return
        if self._pnl_guard_spread_extra > 0 or self._pnl_guard_size_multiplier < 0.999:
            LOG.info("[maker] PnL guard cleared manually")
        self._pnl_guard_spread_extra = 0.0
        self._pnl_guard_size_multiplier = 1.0
        self._pnl_guard_expiry_ts = 0.0
        self._pnl_guard_active_flag = False
        self._set_pnl_guard_flag(False)
        if self.telemetry:
            try:
                self.telemetry.set_gauge("maker_pnl_guard_active", 0.0)
            except Exception:
                pass

    def get_pnl_guard_state(self) -> Dict[str, float]:
        return {
            "extra_spread_bps": float(self._pnl_guard_spread_extra),
            "size_multiplier": float(self._pnl_guard_size_multiplier),
            "expires_at": float(self._pnl_guard_expiry_ts),
            "enabled": float(1.0 if self.pnl_guard_enabled else 0.0),
        }

    def _set_pnl_guard_flag(self, active: bool) -> None:
        if not self.state:
            return
        try:
            if active:
                if hasattr(self.state, "set_flag"):
                    self.state.set_flag("pnl_guard_active", True)
            else:
                if hasattr(self.state, "set_flag"):
                    self.state.set_flag("pnl_guard_active", False)
        except Exception:
            pass

    def _update_volatility(self, mid: Optional[float]) -> float:
        if not self.vol_enabled or mid is None:
            vol = float(self._volatility_ema or 0.0)
            if self.telemetry:
                try:
                    self.telemetry.set_gauge("maker_volatility_bps", vol)
                    self.telemetry.set_gauge("maker_volatility_paused", 0.0)
                except Exception:
                    pass
            return vol

        now = time.time()
        if self._volatility_last_mid is None:
            self._volatility_last_mid = mid
            self._volatility_last_ts = now
            self._volatility_ema = 0.0
            return 0.0

        dt = max(now - self._volatility_last_ts, 1e-6)
        change = abs(mid - self._volatility_last_mid) / max(
            self._volatility_last_mid, 1e-9
        )
        change_bps = change * 10000.0
        alpha = 1 - math.exp(-math.log(2) * dt / self.vol_half_life)
        prev = self._volatility_ema or change_bps
        self._volatility_ema = prev + alpha * (change_bps - prev)

        self._volatility_last_mid = mid
        self._volatility_last_ts = now

        vol = float(self._volatility_ema)
        if self.vol_enabled:
            # High volatility pause (existing logic)
            was_paused = self._volatility_paused
            if not self._volatility_paused and vol >= self.vol_pause_threshold:
                self._volatility_paused = True
                self._volatility_paused_since = time.time()
                LOG.warning(
                    "[maker] volatility %.2fbps above pause threshold %.2fbps; pausing quotes",
                    vol,
                    self.vol_pause_threshold,
                )
            elif self._volatility_paused and vol <= self.vol_resume_threshold:
                if self._can_resume_from_pause():
                    self._volatility_paused = False
                    LOG.info(
                        "[maker] volatility %.2fbps below resume threshold %.2fbps; resuming quotes",
                        vol,
                        self.vol_resume_threshold,
                    )
                    self._volatility_paused_since = None
            if self._volatility_paused and self._volatility_paused_since is None:
                self._volatility_paused_since = time.time()
            if was_paused != self._volatility_paused and self.telemetry:
                LOG.debug(
                    "[maker] volatility pause state changed: %s",
                    "paused" if self._volatility_paused else "active",
                )

            # Low volatility pause (new logic): pause maker when volatility is too low
            # to avoid bleeding on hedging costs
            was_low_vol_paused = self._low_volatility_paused
            if (
                not self._low_volatility_paused
                and vol <= self.vol_low_vol_pause_threshold
                and vol > 0.0  # Don't pause if volatility is exactly 0 (startup)
            ):
                self._low_volatility_paused = True
                self._low_volatility_paused_since = time.time()
                LOG.warning(
                    "[maker] volatility %.2fbps below low-vol pause threshold %.2fbps; pausing quotes to avoid hedging costs",
                    vol,
                    self.vol_low_vol_pause_threshold,
                )
            elif (
                self._low_volatility_paused
                and vol >= self.vol_low_vol_resume_threshold
            ):
                self._low_volatility_paused = False
                LOG.info(
                    "[maker] volatility %.2fbps above low-vol resume threshold %.2fbps; resuming quotes",
                    vol,
                    self.vol_low_vol_resume_threshold,
                )
                self._low_volatility_paused_since = None
            if self._low_volatility_paused and self._low_volatility_paused_since is None:
                self._low_volatility_paused_since = time.time()
            if was_low_vol_paused != self._low_volatility_paused:
                LOG.debug(
                    "[maker] low volatility pause state changed: %s",
                    "paused" if self._low_volatility_paused else "active",
                )

        if self.telemetry:
            try:
                self.telemetry.set_gauge("maker_volatility_bps", float(vol))
                self.telemetry.set_gauge(
                    "maker_volatility_paused", 1.0 if self._volatility_paused else 0.0
                )
                self.telemetry.set_gauge(
                    "maker_low_volatility_paused", 1.0 if self._low_volatility_paused else 0.0
                )
            except Exception:
                pass
        return vol

    def _volatility_factor(self, vol_bps: float) -> float:
        if not self.vol_enabled:
            return 0.0
        if self.vol_high_bps <= self.vol_low_bps:
            return 0.0
        factor = (vol_bps - self.vol_low_bps) / (self.vol_high_bps - self.vol_low_bps)
        return max(0.0, min(1.0, factor))

    def _spread_for_volatility(self, volatility_bps: Optional[float]) -> float:
        if not self.vol_enabled or volatility_bps is None:
            return self.spread_bps
        factor = self._volatility_factor(volatility_bps)
        spread_span = self.vol_max_spread - self.vol_min_spread
        spread = self.vol_min_spread + spread_span * factor
        return max(1e-6, spread)
