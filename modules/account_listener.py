from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

LOG = logging.getLogger("account")


try:
    import websockets  # type: ignore
except Exception:  # pragma: no cover
    websockets = None  # type: ignore


@dataclass(slots=True)
class FillRecord:
    market: str
    side: str
    size: Decimal
    price: Decimal
    timestamp: float
    role: str
    raw: Dict[str, Any]


class AccountListener:
    """
    Minimal account listener that subscribes to trade fills and forwards them
    into the StateStore + optional hedger.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        state: Any = None,
        hedger: Any = None,
        telemetry: Any = None,
    ):
        self.cfg = config or {}
        self.state = state
        self.hedger = hedger
        self.telemetry = telemetry
        self.debug = bool(self.cfg.get("debug", False))
        if self.debug:
            LOG.setLevel(logging.DEBUG)

        ws_cfg = self.cfg.get("ws", {}) if isinstance(self.cfg.get("ws"), dict) else {}
        self.ws_url = ws_cfg.get("url") or "wss://mainnet.zklighter.elliot.ai/stream"
        self.auth_token = ws_cfg.get("auth_token")

        accounts_cfg = ws_cfg.get("accounts")
        if isinstance(accounts_cfg, (list, tuple)):
            self.accounts = [str(x) for x in accounts_cfg]
        elif isinstance(accounts_cfg, str) and accounts_cfg.strip():
            self.accounts = [accounts_cfg.strip()]
        else:
            self.accounts = []

        if not self.accounts:
            api_cfg = self.cfg.get("api") or {}
            acct_idx = api_cfg.get("account_index")
            if acct_idx is not None:
                self.accounts = [str(acct_idx)]

        # optional markets for filtering inventory updates
        maker_cfg = (self.cfg.get("maker") or {}) if isinstance(self.cfg.get("maker"), dict) else {}
        default_market = maker_cfg.get("pair")
        if isinstance(default_market, str) and default_market.startswith("market:"):
            self.market_filter = [default_market]
        else:
            self.market_filter = []

        api_cfg = self.cfg.get("api", {}) if isinstance(self.cfg.get("api"), dict) else {}
        acct_idx = api_cfg.get("account_index")
        self.account_index = str(acct_idx) if acct_idx is not None else None
        if hasattr(self.state, "set_account_index"):
            try:
                self.state.set_account_index(self.account_index)
            except Exception:
                pass

        fees_cfg = self.cfg.get("fees") if isinstance(self.cfg.get("fees"), dict) else {}
        self.maker_fee_actual = Decimal(str(fees_cfg.get("maker_actual_rate", 0)))
        self.taker_fee_actual = Decimal(str(fees_cfg.get("taker_actual_rate", 0)))
        self.maker_fee_premium = Decimal(str(fees_cfg.get("maker_premium_rate", 0.00002)))
        self.taker_fee_premium = Decimal(str(fees_cfg.get("taker_premium_rate", 0.0002)))

        self._stop = asyncio.Event()
        self._spawned = False
        self._fills: deque[FillRecord] = deque(maxlen=1000)

    async def start(self) -> None:
        if self._spawned:
            return
        self._spawned = True
        LOG.info("[account] starting account listener")
        asyncio.create_task(self._run_loop(), name="AccountListenerLoop")

    async def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------ loop
    async def _run_loop(self) -> None:
        if not websockets:
            LOG.warning("[account] websockets module not available, account listener disabled")
            return
        if not self.accounts:
            LOG.warning("[account] no accounts configured; listener idle")
            return

        while not self._stop.is_set():
            try:
                await self._run_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                LOG.exception("[account] listener error: %s", exc)
                await asyncio.sleep(5.0)

    async def _run_once(self) -> None:
        async with websockets.connect(
            self.ws_url,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=10,
        ) as ws:  # type: ignore
            await self._subscribe(ws)
            while not self._stop.is_set():
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=60)  # type: ignore
                    if isinstance(raw_msg, (bytes, bytearray)):
                        raw_msg = raw_msg.decode("utf-8", "ignore")
                    if self.debug:
                        LOG.debug("[account] raw: %s", raw_msg)
                    obj = self._parse_raw(raw_msg)
                    if obj is None:
                        continue

                    msg_type = obj.get("type")
                    if self.debug:
                        LOG.debug("[account] frame: %s", obj)
                    if msg_type == "ping":
                        try:
                            await ws.send(json.dumps({"type": "pong"}))
                            LOG.debug("[account] sent pong response")
                        except Exception as exc:
                            LOG.debug("[account] failed to send pong: %s", exc)
                        continue
                    if msg_type == "connected":
                        await self._subscribe(ws)
                        continue

                    self._handle_obj(obj)
                except asyncio.TimeoutError:
                    LOG.debug("[account] idle ping")
                    continue

    async def _subscribe(self, ws) -> None:
        for acct in self.accounts:
            payload = {"type": "subscribe", "channel": f"account_all/{acct}"}
            if self.auth_token:
                payload["auth"] = self.auth_token
            await ws.send(json.dumps(payload))
            LOG.info("[account] subscribed to account_all/%s", acct)

    def _parse_raw(self, raw: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            LOG.debug("[account] invalid JSON frame: %s", raw)
            return None

    # ---------------------------------------------------------------- frame handling
    def _handle_obj(self, obj: Dict[str, Any]) -> None:
        channel = obj.get("channel", "")
        if isinstance(channel, str) and channel.startswith("account_all:"):
            self._handle_account_all(obj)

    def _handle_account_all(self, obj: Dict[str, Any]) -> None:
        trades = obj.get("trades")
        if isinstance(trades, dict):
            for _trade_id, entry in trades.items():
                if isinstance(entry, list):
                    for sub_entry in entry:
                        self._handle_trade_entry(sub_entry)
                else:
                    self._handle_trade_entry(entry)
        positions = obj.get("positions")
        if isinstance(positions, dict):
            for market_id, entry in positions.items():
                self._handle_position_entry(market_id, entry)

    def _handle_trade_entry(self, entry: Dict[str, Any]) -> None:
        market_id = entry.get("market_id")
        if market_id is None:
            return

        market = f"market:{market_id}"
        if self.market_filter and market not in self.market_filter:
            return

        size = entry.get("base_amount") or entry.get("size")
        price = entry.get("price")
        side = entry.get("side") or entry.get("trade_type")
        ts = float(entry.get("timestamp") or time.time())

        account_id = self.account_index
        role = "maker"
        if account_id is not None:
            ask_id = entry.get("ask_account_id")
            bid_id = entry.get("bid_account_id")
            maker_is_ask = bool(entry.get("is_maker_ask"))
            maker_id = str(ask_id) if maker_is_ask else str(bid_id)
            taker_id = str(bid_id) if maker_is_ask else str(ask_id)
            acct_str = str(account_id)
            if acct_str == maker_id:
                role = "maker"
            elif acct_str == taker_id:
                role = "taker"
            else:
                return
        else:
            ask_id = entry.get("ask_account_id")
            bid_id = entry.get("bid_account_id")
            maker_is_ask = bool(entry.get("is_maker_ask"))
            maker_id = str(ask_id) if maker_is_ask else str(bid_id)
            taker_id = str(bid_id) if maker_is_ask else str(ask_id)
            synced_account = str(entry.get("maker_account_id") or maker_id)
            if hasattr(self.state, "get_account_index"):
                acct_idx = self.state.get_account_index()
                if acct_idx is not None:
                    synced_account = str(acct_idx)
            if synced_account == maker_id:
                role = "maker"
            elif synced_account == taker_id:
                role = "taker"
            else:
                return

        try:
            size_dec = Decimal(str(size))
            price_dec = Decimal(str(price))
        except Exception:
            LOG.debug("[account] bad trade entry: %s", entry)
            return

        fill = FillRecord(
            market=market,
            side=str(side or ""),
            size=size_dec,
            price=price_dec,
            timestamp=ts,
            role=role,
            raw=entry,
        )
        self._fills.append(fill)
        LOG.info("[account] fill %s size=%s price=%s", fill.side, fill.size, fill.price)

        self._update_state(fill)

        if self.telemetry and hasattr(self.telemetry, "touch"):
            try:
                self.telemetry.touch("fill")
            except Exception:
                pass

        if self.hedger and hasattr(self.hedger, "on_fill"):
            try:
                fire_and_forget(self.hedger.on_fill(fill))
            except Exception as exc:
                LOG.debug("[account] hedger on_fill failed: %s", exc)

    def _update_state(self, fill: FillRecord) -> None:
        if not self.state:
            return
        side_lower = fill.side.lower()
        quantity = Decimal("0")
        if side_lower.startswith("open long"):
            quantity = Decimal(fill.size)
        elif side_lower.startswith("close long"):
            quantity = -Decimal(fill.size)
        elif side_lower.startswith("open short"):
            quantity = -Decimal(fill.size)
        elif side_lower.startswith("close short"):
            quantity = Decimal(fill.size)
        else:
            # Fallback: assume positive size increases exposure
            quantity = Decimal(fill.size)

        # Update inventory
        if hasattr(self.state, "update_inventory"):
            try:
                self.state.update_inventory(fill.market, quantity)
            except Exception as exc:
                LOG.debug("[account] state.update_inventory failed: %s", exc)

        if hasattr(self.state, "record_volume_sample"):
            notional = fill.size * fill.price
            if fill.role == "maker":
                fee_actual = notional * self.maker_fee_actual
                fee_premium = notional * self.maker_fee_premium
            else:
                fee_actual = notional * self.taker_fee_actual
                fee_premium = notional * self.taker_fee_premium
            try:
                self.state.record_volume_sample(
                    role=fill.role,
                    notional=notional,
                    fee_actual=fee_actual,
                    fee_premium=fee_premium,
                )
            except Exception as exc:
                LOG.debug("[account] record_volume_sample failed: %s", exc)

        mid_dec: Optional[Decimal] = None
        if hasattr(self.state, "get_mid"):
            try:
                mid_val = self.state.get_mid(fill.market)
                if mid_val is not None:
                    mid_dec = Decimal(str(mid_val))
            except Exception:
                mid_dec = None
        if mid_dec is not None:
            try:
                if fill.role == "maker" and hasattr(self.state, "record_maker_edge"):
                    maker_is_ask = bool(fill.raw.get("is_maker_ask"))
                    if maker_is_ask:
                        edge = (fill.price - mid_dec) * fill.size
                    else:
                        edge = (mid_dec - fill.price) * fill.size
                    if edge > 0:
                        self.state.record_maker_edge(edge)
                elif fill.role == "taker" and hasattr(self.state, "record_taker_slippage"):
                    acct = self.account_index
                    taker_side = None
                    if acct is not None:
                        acct_str = str(acct)
                        if str(fill.raw.get("bid_account_id")) == acct_str:
                            taker_side = "bid"
                        elif str(fill.raw.get("ask_account_id")) == acct_str:
                            taker_side = "ask"
                    if taker_side:
                        if taker_side == "ask":
                            slip = (mid_dec - fill.price) * fill.size
                        else:
                            slip = (fill.price - mid_dec) * fill.size
                        self.state.record_taker_slippage(abs(slip))
            except Exception as exc:
                LOG.debug("[account] edge tracking failed: %s", exc)

    def _handle_position_entry(self, market_id: str, entry: Dict[str, Any]) -> None:
        market = f"market:{market_id}"
        if self.market_filter and market not in self.market_filter:
            return
        position = entry.get("position")
        if position is None:
            return
        try:
            value = Decimal(str(position))
        except Exception:
            LOG.debug("[account] bad position entry: %s", entry)
            return
        sign_indicator = entry.get("sign")
        try:
            if isinstance(sign_indicator, (int, float)) and sign_indicator < 0:
                value = -value
            elif isinstance(sign_indicator, str):
                if sign_indicator.strip() == "-1":
                    value = -value
        except Exception:
            pass
        if not self.state or not hasattr(self.state, "set_inventory"):
            return
        try:
            self.state.set_inventory(market, value)
            LOG.debug("[account] position updated %s -> %s", market, value)
        except Exception as exc:
            LOG.debug("[account] state.set_inventory failed: %s", exc)


def fire_and_forget(coro):
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        pass


