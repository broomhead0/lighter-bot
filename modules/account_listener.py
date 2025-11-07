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
                    obj = self._parse_raw(raw_msg)
                    if obj is None:
                        continue

                    msg_type = obj.get("type")
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
        if isinstance(trades, list):
            for entry in trades:
                self._handle_trade_entry(entry)

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


def fire_and_forget(coro):
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        pass


