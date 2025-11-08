# modules/maker_engine.py
import asyncio
import logging
import math
import random
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

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
        self.size = float(maker_cfg.get("size", 0.001))
        self.spread_bps = float(maker_cfg.get("spread_bps", 10.0))  # 10 bps default
        self.refresh_seconds = float(maker_cfg.get("refresh_seconds", 5.0))
        self.randomize_bps = float(
            maker_cfg.get("randomize_bps", 4.0)
        )  # random widen/narrow
        self.allow_synthetic_fallback = bool(maker_cfg.get("synthetic_fallback", False))

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

    async def run(self):
        LOG.info("MakerEngine started for %s", self.market)
        try:
            while not self._stop.is_set():
                mid = await self._get_mid()
                if mid is None:
                    LOG.info("[maker] waiting for mid...")
                    await asyncio.sleep(1.0)
                    continue

                bid, ask, spread = self._compute_quotes(mid)

                # Check cancel discipline (throttle if exceeded)
                self._check_cancel_discipline()

                # Guard: validate quotes before posting
                if self.guard:
                    if not self.guard.is_allowed(
                        Decimal(str(mid)),
                        Decimal(str(bid)),
                        Decimal(str(ask)),
                        self.market
                    ):
                        LOG.warning(
                            "[maker] quote blocked by guard: mid=%.4f bid=%.4f ask=%.4f",
                            mid, bid, ask
                        )
                        await self._cancel_all_orders()
                        await asyncio.sleep(self.refresh_seconds)
                        continue

                # Chaos: force cancel if testing cancel discipline
                if self.chaos and self.chaos.should_force_cancel():
                    LOG.warning(
                        "[maker] CHAOS: forcing cancel (testing cancel discipline)"
                    )
                    self._record_cancel()

                await self._post_quotes(bid, ask, self.size)

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

    def _compute_quotes(self, mid: float) -> Tuple[float, float, float]:
        jitter = random.uniform(-self.randomize_bps, self.randomize_bps)
        bps = max(1e-6, self.spread_bps + jitter)

        # Apply chaos quote-width spikes if enabled
        if self.chaos:
            bps = self.chaos.modify_quote_spread(bps)

        half = (bps / 20000.0) * mid  # half-spread in price units
        bid = max(0.0000001, mid - half)
        ask = mid + half
        return bid, ask, bps

    async def _post_quotes(self, bid: float, ask: float, size: float):
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
                await self._place_order("bid", bid, size)
                await self._place_order("ask", ask, size)
            except Exception as e:
                LOG.error(f"[maker] failed to place orders: {e}")
                await self._alert("error", "Order placement failed", str(e))
        else:
            # Dry-run mode: just log
            LOG.debug(
                "[maker] DRY-RUN: would place bid=%.4f ask=%.4f size=%.6f",
                bid, ask, size
            )

    def _touch_quote(self):
        if getattr(self, "telemetry", None):
            try:
                self.telemetry.touch("quote")
            except Exception:
                pass

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
