from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, Optional

from core.trading_client import TradingClient, TradingConfig, SignerClient

LOG = logging.getLogger("hedger")


class Hedger:
    """
    Simple inventory hedger that watches `StateStore` inventory and submits
    aggressive limit orders to bring exposure back inside configured bands.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        state: Any = None,
        telemetry: Any = None,
        alert_manager: Any = None,
        trading_client: Optional[TradingClient] = None,
    ):
        self.cfg = config or {}
        self.state = state
        self.telemetry = telemetry
        self.alerts = alert_manager

        hedger_cfg = (
            self.cfg.get("hedger") or {}
            if isinstance(self.cfg.get("hedger"), dict)
            else {}
        )
        maker_cfg = (
            self.cfg.get("maker") or {}
            if isinstance(self.cfg.get("maker"), dict)
            else {}
        )

        self.enabled = bool(hedger_cfg.get("enabled", False))
        self.market = (
            hedger_cfg.get("market") or maker_cfg.get("pair") or "market:1"
        )

        LOG.info(
            "[hedger] config snapshot dry_run=%s trigger_units=%s trigger_notional=%s",
            hedger_cfg.get("dry_run", maker_cfg.get("dry_run", True)),
            hedger_cfg.get("trigger_units"),
            hedger_cfg.get("trigger_notional"),
        )
        self._explicit_dry_run = "dry_run" in hedger_cfg
        self.trigger_units = Decimal(
            str(hedger_cfg.get("trigger_units", 0.05))
        )
        if (
            hedger_cfg.get("trigger_notional") is not None
            and hedger_cfg.get("trigger_notional") != "none"
        ):
            self.trigger_notional: Optional[Decimal] = Decimal(
                str(hedger_cfg.get("trigger_notional", 0))
            )
        else:
            self.trigger_notional = None
        self.target_units = Decimal(str(hedger_cfg.get("target_units", 0)))
        self.max_clip_units = Decimal(
            str(hedger_cfg.get("max_clip_units", maker_cfg.get("size", 0.05)))
        )
        self.price_offset_bps = float(hedger_cfg.get("price_offset_bps", 8.0))
        self.poll_interval_s = float(hedger_cfg.get("poll_interval_seconds", 1.5))
        self.cooldown_seconds = float(hedger_cfg.get("cooldown_seconds", 5.0))
        self.max_slippage_bps = float(hedger_cfg.get("max_slippage_bps", 12.0))
        self.max_attempts = int(hedger_cfg.get("max_attempts", 3))
        self.retry_backoff_s = float(hedger_cfg.get("retry_backoff_seconds", 2.0))
        fees_cfg = self.cfg.get("fees") if isinstance(self.cfg.get("fees"), dict) else {}
        self.taker_fee_actual = Decimal(str(fees_cfg.get("taker_actual_rate", 0)))
        self.taker_fee_premium = Decimal(str(fees_cfg.get("taker_premium_rate", 0.0002)))

        self.dry_run = bool(hedger_cfg.get("dry_run", maker_cfg.get("dry_run", True)))
        self.prefer_passive = bool(hedger_cfg.get("prefer_passive", True))
        self.passive_wait_seconds = float(hedger_cfg.get("passive_wait_seconds", 1.0))
        self.passive_offset_bps = float(
            hedger_cfg.get("passive_offset_bps", max(1.0, self.price_offset_bps / 2))
        )
        self.passive_timeout_seconds = float(
            hedger_cfg.get("passive_timeout_seconds", 0.0)
        )
        default_guard_seconds = 0.0
        if self.passive_timeout_seconds > 0:
            default_guard_seconds = self.passive_timeout_seconds + 2.0
        self.guard_emergency_seconds = float(
            hedger_cfg.get("guard_emergency_seconds", default_guard_seconds)
        )
        self.guard_emergency_clip_multiplier = float(
            hedger_cfg.get("guard_emergency_clip_multiplier", 1.2)
        )
        self.guard_emergency_extra_bps = float(
            hedger_cfg.get("guard_emergency_extra_bps", 4.0)
        )
        self.guard_emergency_cooldown = float(
            hedger_cfg.get(
                "guard_emergency_cooldown_seconds", min(self.cooldown_seconds, 1.0)
            )
        )
        self.guard_clip_multiplier = float(
            hedger_cfg.get("guard_clip_multiplier", 0.75)
        )
        self.guard_price_offset_bps = float(
            hedger_cfg.get("guard_price_offset_bps", self.price_offset_bps)
        )
        self.guard_max_slippage_bps = float(
            hedger_cfg.get("guard_max_slippage_bps", self.max_slippage_bps)
        )

        # If taker fees are zero (standard tier), force dry-run to avoid accidental cost.
        if self.taker_fee_actual == Decimal("0") and not self._explicit_dry_run:
            if not self.dry_run:
                LOG.info("[hedger] forcing dry-run mode while taker fees are zero-tier")
            self.dry_run = True

        api_cfg = self.cfg.get("api") or {}
        trading_cfg = self._build_trading_config(api_cfg, maker_cfg)
        self._trading_client: Optional[TradingClient] = trading_client
        self._owns_trading_client = False
        if self._trading_client is None and trading_cfg:
            try:
                self._trading_client = TradingClient(trading_cfg)
                self._owns_trading_client = True
                LOG.info("[hedger] trading client ready for live hedges")
            except Exception as exc:
                LOG.warning("[hedger] trading client unavailable: %s", exc)

        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._loop_task: Optional[asyncio.Task] = None
        self._next_allowed_ts = 0.0
        self._open_passive_orders: set[int] = set()
        self._over_trigger_since: Optional[float] = None

    async def start(self) -> None:
        if self._loop_task or not self.enabled:
            if not self.enabled:
                LOG.info("[hedger] disabled via config")
            return
        LOG.info("[hedger] starting hedger loop for %s", self.market)
        self._loop_task = asyncio.create_task(self._run_loop(), name="HedgerLoop")

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._loop_task:
            self._loop_task.cancel()
        if self._owns_trading_client and self._trading_client:
            try:
                await self._trading_client.close()
            except Exception as exc:
                LOG.debug("[hedger] trading client close failed: %s", exc)

    async def on_fill(self, _fill: Any) -> None:
        """Wake hedger on new fills to react quickly."""
        self._wake.set()

    # ------------------------------------------------------------------ private

    async def _run_loop(self) -> None:
        last_heartbeat = 0.0
        try:
            while not self._stop.is_set():
                try:
                    # Heartbeat every 60 seconds to confirm loop is running
                    now = time.time()
                    if now - last_heartbeat > 60.0:
                        inv = None
                        if self.state and hasattr(self.state, "get_inventory"):
                            try:
                                inv = self.state.get_inventory(self.market)
                            except Exception:
                                pass
                        LOG.debug("[hedger] loop heartbeat: enabled=%s inv=%s", self.enabled, inv)
                        last_heartbeat = now
                    
                    await self._maybe_hedge()
                except Exception as exc:
                    LOG.exception("[hedger] loop error: %s", exc)
                await self._wait_for_next_tick()
        except asyncio.CancelledError:
            LOG.debug("[hedger] loop cancelled")

    async def _wait_for_next_tick(self) -> None:
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=self.poll_interval_s)
        except asyncio.TimeoutError:
            pass
        finally:
            self._wake.clear()

    async def _maybe_hedge(self) -> None:
        if not self.enabled:
            return
        if not self.state or not hasattr(self.state, "get_inventory"):
            LOG.debug("[hedger] state store missing inventory")
            return

        inventory = self.state.get_inventory(self.market)
        if inventory is None:
            LOG.debug("[hedger] inventory is None for %s", self.market)
            return
        if not isinstance(inventory, Decimal):
            try:
                inventory = Decimal(str(inventory))
            except Exception:
                LOG.debug("[hedger] inventory not decimal: %s", inventory)
                return

        abs_inv = abs(inventory)
        now = time.time()
        
        # Log inventory check for debugging (always log when significantly over threshold)
        if abs_inv > self.trigger_units * Decimal("1.5"):  # Only log when significantly over trigger
            LOG.info(
                "[hedger] inventory check: inv=%.4f trigger=%.4f target=%.4f (over threshold by %.4f)",
                float(abs_inv),
                float(self.trigger_units),
                float(self.target_units),
                float(abs_inv - self.trigger_units),
            )
        
        if abs_inv <= self.trigger_units:
            self._over_trigger_since = None
            if self.telemetry:
                try:
                    self.telemetry.set_gauge("hedger_force_aggressive", 0.0)
                    self.telemetry.set_gauge("hedger_guard_emergency", 0.0)
                except Exception:
                    pass
            return
        if self._over_trigger_since is None:
            self._over_trigger_since = now
            LOG.info("[hedger] inventory exceeded trigger: %.4f > %.4f", float(abs_inv), float(self.trigger_units))

        mid = self._get_mid_price()
        if mid is None:
            LOG.warning("[hedger] no mid price available for %s", self.market)
            return

        guard_block_age = None
        guard_emergency_active = False
        if (
            self.guard_emergency_seconds > 0.0
            and self.state
            and hasattr(self.state, "get_guard_block_since")
        ):
            try:
                guard_since_val = self.state.get_guard_block_since(self.market)
            except Exception:
                guard_since_val = None
            if guard_since_val is not None:
                try:
                    guard_ts = float(guard_since_val)
                    guard_block_age = now - guard_ts
                    if guard_block_age >= self.guard_emergency_seconds:
                        guard_emergency_active = True
                        LOG.warning("[hedger] guard emergency active: block_age=%.1fs", guard_block_age)
                except Exception:
                    guard_block_age = None

        pnl_guard_active = False
        if self.state and hasattr(self.state, "get_flag"):
            try:
                flag = self.state.get_flag("pnl_guard_active")
                pnl_guard_active = bool(flag)
            except Exception:
                pnl_guard_active = False

        if self.trigger_notional is not None:
            notional = abs_inv * Decimal(str(mid))
            if notional <= self.trigger_notional:
                LOG.debug("[hedger] notional check failed: %.2f <= %.2f", float(notional), float(self.trigger_notional))
                return
            LOG.debug("[hedger] notional check passed: %.2f > %.2f", float(notional), float(self.trigger_notional))

        excess_units = abs_inv - self.target_units
        if excess_units <= Decimal("0"):
            LOG.debug("[hedger] excess units <= 0: %.4f", float(excess_units))
            return

        clip_limit = self.max_clip_units
        if guard_emergency_active and self.guard_emergency_clip_multiplier > 1.0:
            try:
                clip_limit = self.max_clip_units * Decimal(
                    str(self.guard_emergency_clip_multiplier)
                )
            except Exception:
                clip_limit = self.max_clip_units
            if clip_limit > abs_inv:
                clip_limit = abs_inv
        hedge_units = min(excess_units, clip_limit)
        LOG.debug("[hedger] initial hedge_units: %.4f (excess=%.4f, clip_limit=%.4f)", 
                  float(hedge_units), float(excess_units), float(clip_limit))
        
        if pnl_guard_active and self.guard_clip_multiplier > 0:
            try:
                guard_clip = self.max_clip_units * Decimal(str(self.guard_clip_multiplier))
                hedge_units = min(hedge_units, guard_clip)
                LOG.debug("[hedger] pnl guard active, reduced hedge_units to: %.4f (guard_clip=%.4f)",
                          float(hedge_units), float(guard_clip))
            except Exception:
                pass
        if hedge_units <= Decimal("0"):
            LOG.warning("[hedger] hedge_units <= 0 after guard adjustment: %.4f", float(hedge_units))
            return

        side = "ask" if inventory > 0 else "bid"

        prefer_passive = self.prefer_passive
        force_aggressive = False
        if guard_emergency_active:
            prefer_passive = False
            force_aggressive = True
        elif (
            self.passive_timeout_seconds > 0.0
            and self._over_trigger_since is not None
            and (now - self._over_trigger_since) >= self.passive_timeout_seconds
        ):
            prefer_passive = False
            force_aggressive = self.prefer_passive

        price_offset_bps = self.price_offset_bps
        if pnl_guard_active:
            price_offset_bps = self.guard_price_offset_bps
        if guard_emergency_active:
            price_offset_bps += self.guard_emergency_extra_bps
        price = self._aggressive_price(mid, side, offset_bps=price_offset_bps)

        if self.telemetry:
            try:
                self.telemetry.set_gauge(
                    "hedger_force_aggressive", 1.0 if force_aggressive else 0.0
                )
                self.telemetry.set_gauge(
                    "hedger_guard_emergency", 1.0 if guard_emergency_active else 0.0
                )
            except Exception:
                pass

        if guard_emergency_active:
            self._next_allowed_ts = 0.0

        max_slippage_bps = self.max_slippage_bps
        if pnl_guard_active:
            max_slippage_bps = self.guard_max_slippage_bps

        if time.time() < self._next_allowed_ts:
            remaining = self._next_allowed_ts - time.time()
            LOG.info("[hedger] cooling down (%.2fs remaining, inv=%.4f, hedge_units=%.4f)", 
                     remaining, float(abs_inv), float(hedge_units))
            return

        LOG.info("[hedger] executing hedge: side=%s units=%.4f price=%.4f inv=%.4f mid=%.4f",
                 side, float(hedge_units), price, float(abs_inv), mid)
        success = await self._execute_hedge(
            side=side,
            size=float(hedge_units),
            price=price,
            mid=mid,
            abs_inventory=abs_inv,
            prefer_passive=prefer_passive,
            max_slippage_bps=max_slippage_bps,
        )
        if success and self.telemetry and hasattr(self.telemetry, "touch"):
            try:
                self.telemetry.touch("hedge")
            except Exception:
                pass

        cooldown = self.cooldown_seconds
        if guard_emergency_active and self.guard_emergency_cooldown is not None:
            cooldown = max(0.1, float(self.guard_emergency_cooldown))
        self._next_allowed_ts = time.time() + cooldown
        if success:
            self._over_trigger_since = None

    def _get_mid_price(self) -> Optional[float]:
        if self.state and hasattr(self.state, "get_mid"):
            try:
                mid = self.state.get_mid(self.market)
                if mid is not None:
                    return float(mid)
            except Exception:
                pass
        return None

    def _aggressive_price(self, mid: float, side: str, offset_bps: Optional[float] = None) -> float:
        if offset_bps is None:
            offset_bps = self.price_offset_bps
        offset_bps = max(0.0, float(offset_bps))
        offset = (offset_bps / 10_000.0) * mid
        if side == "ask":
            return max(0.0, mid - offset)
        return mid + offset

    def _passive_price(self, mid: float, side: str) -> float:
        offset = (self.passive_offset_bps / 10_000.0) * mid
        if side == "ask":
            return max(0.0, mid + offset)
        return max(0.0, mid - offset)

    async def _execute_hedge(
        self,
        side: str,
        size: float,
        price: float,
        mid: Optional[float] = None,
        abs_inventory: Decimal = Decimal("0"),
        prefer_passive: Optional[bool] = None,
        max_slippage_bps: Optional[float] = None,
    ) -> bool:
        size_dec = Decimal(str(size))
        price_dec = Decimal(str(price))
        notional = size_dec * price_dec

        use_passive = self.prefer_passive if prefer_passive is None else bool(prefer_passive)

        if (
            use_passive
            and not self.dry_run
            and self._trading_client
            and mid is not None
        ):
            mid_dec = Decimal(str(mid))
            passive_success = await self._execute_passive_hedge(
                side=side,
                size=size_dec,
                mid=mid_dec,
                abs_inventory=abs_inventory,
            )
            if passive_success:
                self._record_simulated_slippage(notional, Decimal("0"))
                return True
        fee_actual = notional * self.taker_fee_actual
        fee_premium = notional * self.taker_fee_premium
        slip_value: Optional[Decimal] = None
        if mid is not None:
            try:
                mid_dec = Decimal(str(mid))
                slip_value = abs(mid_dec - price_dec) * size_dec
                slip_bps = abs(mid_dec - price_dec) / mid_dec * Decimal("10000") if mid_dec != 0 else None
            except Exception:
                slip_value = None
                slip_bps = None
        else:
            slip_bps = None

        slippage_cap = self.max_slippage_bps if max_slippage_bps is None else float(max_slippage_bps)
        if slip_bps is not None and slippage_cap > 0 and float(slip_bps) > slippage_cap:
            LOG.warning(
                "[hedger] skipping hedge (slippage %.2fbps exceeds cap %.2fbps)",
                float(slip_bps),
                slippage_cap,
            )
            return False

        LOG.info(
            "[hedger] hedging %s %.6f at %.4f (dry_run=%s) notional=%.6f est_fee_premium=%.8f",
            side,
            size,
            price,
            self.dry_run,
            notional,
            fee_premium,
        )

        if hasattr(self.state, "record_hedger_simulation"):
            try:
                self.state.record_hedger_simulation(notional=notional, fee_premium=fee_premium)
            except Exception:
                pass

        if self.dry_run:
            self._record_simulated_slippage(notional, slip_value)
            return True

        if not self._trading_client:
            LOG.warning("[hedger] trading client not available; cannot hedge")
            return False

        attempts = 0
        tif_ioc = None
        if SignerClient is not None and hasattr(SignerClient, "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL"):
            tif_ioc = SignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL

        while attempts < self.max_attempts and not self._stop.is_set():
            attempts += 1
            try:
                await self._trading_client.ensure_ready()
                order = await self._trading_client.create_limit_order(
                    market=self.market,
                    side=side,
                    price=price,
                    size=size,
                    reduce_only=True,
                    post_only=False,
                    time_in_force=tif_ioc,
                )
                LOG.info(
                    "[hedger] submitted hedge order idx=%s size=%.6f price=%.4f tx=%s premium_fee_est=%.8f actual_fee_est=%.8f",
                    order.client_order_index,
                    size,
                    price,
                    order.tx_hash,
                    fee_premium,
                    fee_actual,
                )
                self._record_simulated_slippage(notional, slip_value)
                return True
            except Exception as exc:
                LOG.warning("[hedger] hedge attempt %s failed: %s", attempts, exc)
                if attempts < self.max_attempts:
                    await asyncio.sleep(self.retry_backoff_s)

        await self._alert(
            "warning",
            "Hedge attempts exhausted",
            f"Unable to hedge exposure {self.market} size={size} side={side}",
        )
        return False

    async def _execute_passive_hedge(
        self,
        side: str,
        size: Decimal,
        mid: Decimal,
        abs_inventory: Decimal,
    ) -> bool:
        if not self._trading_client:
            return False

        passive_price = self._passive_price(float(mid), side)
        try:
            await self._trading_client.ensure_ready()
            order = await self._trading_client.create_post_only_limit(
                market=self.market,
                side=side,
                price=passive_price,
                size=float(size),
                reduce_only=True,
            )
        except Exception as exc:
            LOG.debug("[hedger] passive hedge placement failed: %s", exc)
            return False

        client_index = int(order.client_order_index)
        self._open_passive_orders.add(client_index)
        LOG.info(
            "[hedger] resting passive %s order idx=%s size=%.6f price=%.4f",
            side,
            client_index,
            float(size),
            passive_price,
        )

        deadline = time.time() + self.passive_wait_seconds
        success = False
        start_abs = abs_inventory

        while time.time() < deadline and not self._stop.is_set():
            await asyncio.sleep(0.3)
            current = None
            if self.state and hasattr(self.state, "get_inventory"):
                try:
                    current = self.state.get_inventory(self.market)
                except Exception:
                    current = None
            if current is None:
                continue
            try:
                current_abs = abs(Decimal(str(current)))
            except Exception:
                continue
            if current_abs <= self.trigger_units:
                success = True
                break
            if start_abs - current_abs >= size * Decimal("0.6"):
                success = True
                break

        if not success:
            try:
                await self._trading_client.cancel_order(
                    market=self.market, client_order_index=client_index
                )
            except Exception as exc:
                LOG.debug("[hedger] passive hedge cancel failed: %s", exc)
            finally:
                self._open_passive_orders.discard(client_index)
            LOG.debug("[hedger] passive hedge timed out; falling back to aggressive")
            return False

        self._open_passive_orders.discard(client_index)
        LOG.info("[hedger] passive hedge filled for idx=%s", client_index)
        return True

    async def _alert(self, level: str, title: str, message: str) -> None:
        if self.alerts and hasattr(self.alerts, level):
            try:
                await getattr(self.alerts, level)(title, message)
            except Exception:
                pass

    def _record_simulated_slippage(
        self,
        notional: Decimal,
        slip_value: Optional[Decimal],
    ) -> None:
        if (
            self.dry_run
            and slip_value is not None
            and self.state
            and hasattr(self.state, "record_taker_slippage")
        ):
            try:
                self.state.record_taker_slippage(slip_value)
            except Exception:
                pass
        if self.dry_run and self.state and hasattr(self.state, "record_volume_sample"):
            try:
                self.state.record_volume_sample(
                    role="taker",
                    notional=notional,
                    fee_actual=notional * self.taker_fee_actual,
                    fee_premium=notional * self.taker_fee_premium,
                )
            except Exception:
                pass

    def _build_trading_config(
        self,
        api_cfg: Dict[str, Any],
        maker_cfg: Dict[str, Any],
    ) -> Optional[TradingConfig]:
        base_url = api_cfg.get("base_url")
        private_key = api_cfg.get("private_key") or api_cfg.get("key")
        account_index = api_cfg.get("account_index")
        api_key_index = api_cfg.get("api_key_index")

        if not (base_url and private_key and account_index is not None and api_key_index is not None):
            return None

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
                    int(api_cfg["max_api_key_index"])
                    if api_cfg.get("max_api_key_index") is not None
                    else None
                ),
                nonce_management=api_cfg.get("nonce_management"),
            )
        except Exception as exc:
            LOG.warning("[hedger] invalid trading config: %s", exc)
            return None

