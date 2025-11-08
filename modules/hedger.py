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
        self.max_attempts = int(hedger_cfg.get("max_attempts", 3))
        self.retry_backoff_s = float(hedger_cfg.get("retry_backoff_seconds", 2.0))
        fees_cfg = self.cfg.get("fees") if isinstance(self.cfg.get("fees"), dict) else {}
        self.taker_fee_actual = Decimal(str(fees_cfg.get("taker_actual_rate", 0)))
        self.taker_fee_premium = Decimal(str(fees_cfg.get("taker_premium_rate", 0.0002)))

        self.dry_run = bool(hedger_cfg.get("dry_run", maker_cfg.get("dry_run", True)))

        # If taker fees are zero (standard tier), force dry-run to avoid accidental cost.
        if self.taker_fee_actual == Decimal("0"):
            if not self.dry_run:
                LOG.info("[hedger] forcing dry-run mode while taker fees are zero-tier")
            self.dry_run = True

        api_cfg = self.cfg.get("api") or {}
        trading_cfg = self._build_trading_config(api_cfg, maker_cfg)
        self._trading_client: Optional[TradingClient] = None
        if trading_cfg:
            try:
                self._trading_client = TradingClient(trading_cfg)
                LOG.info("[hedger] trading client ready for live hedges")
            except Exception as exc:
                LOG.warning("[hedger] trading client unavailable: %s", exc)

        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._loop_task: Optional[asyncio.Task] = None
        self._next_allowed_ts = 0.0

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
        if self._trading_client:
            try:
                await self._trading_client.close()
            except Exception as exc:
                LOG.debug("[hedger] trading client close failed: %s", exc)

    async def on_fill(self, _fill: Any) -> None:
        """Wake hedger on new fills to react quickly."""
        self._wake.set()

    # ------------------------------------------------------------------ private

    async def _run_loop(self) -> None:
        try:
            while not self._stop.is_set():
                try:
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
            return
        if not isinstance(inventory, Decimal):
            try:
                inventory = Decimal(str(inventory))
            except Exception:
                LOG.debug("[hedger] inventory not decimal: %s", inventory)
                return

        abs_inv = abs(inventory)
        if abs_inv <= self.trigger_units:
            return

        mid = self._get_mid_price()
        if mid is None:
            LOG.debug("[hedger] no mid price available for %s", self.market)
            return

        if self.trigger_notional is not None:
            notional = abs_inv * Decimal(str(mid))
            if notional <= self.trigger_notional:
                return

        excess_units = abs_inv - self.target_units
        if excess_units <= Decimal("0"):
            return

        hedge_units = min(excess_units, self.max_clip_units)
        if hedge_units <= Decimal("0"):
            return

        side = "ask" if inventory > 0 else "bid"
        price = self._aggressive_price(mid, side)

        if time.time() < self._next_allowed_ts:
            LOG.debug("[hedger] cooling down (%.2fs remaining)", self._next_allowed_ts - time.time())
            return

        success = await self._execute_hedge(side, float(hedge_units), price)
        if success and self.telemetry and hasattr(self.telemetry, "touch"):
            try:
                self.telemetry.touch("hedge")
            except Exception:
                pass

        self._next_allowed_ts = time.time() + self.cooldown_seconds

    def _get_mid_price(self) -> Optional[float]:
        if self.state and hasattr(self.state, "get_mid"):
            try:
                mid = self.state.get_mid(self.market)
                if mid is not None:
                    return float(mid)
            except Exception:
                pass
        return None

    def _aggressive_price(self, mid: float, side: str) -> float:
        offset = (self.price_offset_bps / 10_000.0) * mid
        if side == "ask":
            return max(0.0, mid - offset)
        return mid + offset

    async def _execute_hedge(self, side: str, size: float, price: float) -> bool:
        notional = Decimal(str(size)) * Decimal(str(price))
        fee_actual = notional * self.taker_fee_actual
        fee_premium = notional * self.taker_fee_premium

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

    async def _alert(self, level: str, title: str, message: str) -> None:
        if self.alerts and hasattr(self.alerts, level):
            try:
                await getattr(self.alerts, level)(title, message)
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

