from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

try:
    from metrics.ledger import FillEvent
except Exception:  # pragma: no cover
    FillEvent = None  # type: ignore

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
        metrics_ledger: Any = None,
    ):
        self.cfg = config or {}
        self.state = state
        self.hedger = hedger
        self.telemetry = telemetry
        self.metrics_ledger = metrics_ledger
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
        self.default_market = maker_cfg.get("pair") if isinstance(maker_cfg.get("pair"), str) else None
        default_market = maker_cfg.get("pair")
        if isinstance(default_market, str) and default_market.startswith("market:"):
            self.market_filter = [default_market]
        else:
            self.market_filter = []

        api_cfg = self.cfg.get("api", {}) if isinstance(self.cfg.get("api"), dict) else {}
        acct_idx = api_cfg.get("account_index")
        self.account_index = str(acct_idx) if acct_idx is not None else None
        try:
            self._account_index_int: Optional[int] = int(acct_idx) if acct_idx is not None else None
        except Exception:
            self._account_index_int = None
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
        self._fifo_lots: Dict[str, deque] = defaultdict(deque)
        self._fifo_realized_quote: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

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
            seen: set[str] = set()
            for market_id, entry in positions.items():
                self._handle_position_entry(market_id, entry)
                seen.add(str(market_id))
            # Reset inventory for tracked markets not present in positions update
            # This ensures StateStore stays in sync with exchange positions
            for market in self._tracked_markets():
                key = market.split(":", 1)[-1]
                if key not in seen:
                    self._reset_position(market)
        else:
            for market in self._tracked_markets():
                self._reset_position(market)

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
        base_delta = self._compute_base_delta(fill)
        try:
            fill.side = "bid" if base_delta > 0 else "ask"
        except Exception:
            pass

        # Update inventory
        if hasattr(self.state, "update_inventory"):
            try:
                self.state.update_inventory(fill.market, base_delta)
            except Exception as exc:
                LOG.debug("[account] state.update_inventory failed: %s", exc)

        notional = fill.size * fill.price
        if fill.role == "maker":
            fee_actual = notional * self.maker_fee_actual
            fee_premium = notional * self.maker_fee_premium
        else:
            fee_actual = notional * self.taker_fee_actual
            fee_premium = notional * self.taker_fee_premium

        if hasattr(self.state, "record_volume_sample"):
            try:
                self.state.record_volume_sample(
                    role=fill.role,
                    notional=notional,
                    fee_actual=fee_actual,
                    fee_premium=fee_premium,
                )
            except Exception as exc:
                LOG.debug("[account] record_volume_sample failed: %s", exc)

        quote_delta = -(base_delta * fill.price)
        if hasattr(self.state, "record_cash_flow"):
            try:
                self.state.record_cash_flow(quote_delta, fee_actual)
            except Exception as exc:
                LOG.debug("[account] record_cash_flow failed: %s", exc)

        fifo_realized_delta = self._update_fifo_realized(fill, base_delta, fee_actual)
        if fifo_realized_delta is not None and self.telemetry:
            try:
                total_fifo = sum(self._fifo_realized_quote.values(), Decimal("0"))
                self.telemetry.set_gauge("maker_fifo_realized_quote", float(total_fifo))
                for market, value in self._fifo_realized_quote.items():
                    gauge = f"maker_fifo_realized_quote_{market.replace(':', '_')}"
                    self.telemetry.set_gauge(gauge, float(value))
            except Exception:
                pass

        mid_dec: Optional[Decimal] = None
        if hasattr(self.state, "get_mid"):
            try:
                mid_val = self.state.get_mid(fill.market)
                if mid_val is not None:
                    mid_dec = Decimal(str(mid_val))
            except Exception:
                mid_dec = None

        if self.metrics_ledger and FillEvent:
            try:
                mid_value = None
                if mid_dec is not None:
                    mid_value = str(mid_dec)
                event = FillEvent(
                    timestamp=fill.timestamp,
                    market=fill.market,
                    role=fill.role,
                    side="bid" if base_delta > 0 else "ask",
                    size=str(fill.size),
                    price=str(fill.price),
                    notional=str(notional),
                    base_delta=str(base_delta),
                    quote_delta=str(quote_delta),
                    fee_paid=str(fee_actual),
                    mid_price=mid_value,
                    trade_id=fill.raw.get("trade_id"),
                    source="account_listener",
                )
                self.metrics_ledger.append(event)
            except Exception as exc:
                LOG.debug("[account] ledger append failed: %s", exc)
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

    def _update_fifo_realized(
        self,
        fill: FillRecord,
        base_delta: Decimal,
        fee_actual: Decimal,
    ) -> Optional[Decimal]:
        if fill.role.lower() != "maker":
            return None

        lots = self._fifo_lots[fill.market]
        realized = Decimal("0")

        if base_delta > 0:
            remaining = base_delta
            while lots and lots[0][0] < 0 and remaining > 0:
                short_lot = lots[0]
                lot_size, lot_price = short_lot
                matched = min(remaining, -lot_size)
                realized += (lot_price - fill.price) * matched
                lot_size += matched  # lot_size is negative
                remaining -= matched
                if lot_size == 0:
                    lots.popleft()
                else:
                    short_lot[0] = lot_size
            if remaining > 0:
                lots.append([remaining, fill.price])
        elif base_delta < 0:
            remaining = -base_delta
            while lots and lots[0][0] > 0 and remaining > 0:
                long_lot = lots[0]
                lot_size, lot_price = long_lot
                matched = min(remaining, lot_size)
                realized += (fill.price - lot_price) * matched
                lot_size -= matched
                remaining -= matched
                if lot_size == 0:
                    lots.popleft()
                else:
                    long_lot[0] = lot_size
            if remaining > 0:
                lots.appendleft([-remaining, fill.price])

        realized -= fee_actual
        current = self._fifo_realized_quote[fill.market]
        self._fifo_realized_quote[fill.market] = current + realized
        return realized

    def _handle_position_entry(self, market_id: str, entry: Dict[str, Any]) -> None:
        market = f"market:{market_id}"
        if self.market_filter and market not in self.market_filter:
            return
        position = entry.get("position")
        if position is None:
            self._reset_position(market)
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
        self._set_inventory(market, value)

        # Log position updates with PnL for analysis (source of truth from exchange!)
        # This matches UI PnL exactly - much simpler than reconstructing from trades!
        realized_pnl = entry.get("realized_pnl")
        unrealized_pnl = entry.get("unrealized_pnl")
        if realized_pnl is not None:
            try:
                import json
                import time as time_module
                from pathlib import Path

                # Simple JSONL file to track position updates (source of truth!)
                positions_file = Path("data/metrics/positions.jsonl")
                positions_file.parent.mkdir(parents=True, exist_ok=True)

                position_update = {
                    "timestamp": time_module.time(),
                    "market": market,
                    "position": str(value),
                    "realized_pnl": float(realized_pnl),
                    "unrealized_pnl": float(unrealized_pnl or 0),
                    "total_pnl": float(realized_pnl) + float(unrealized_pnl or 0),
                }

                # Append to JSONL file
                with positions_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(position_update, separators=(",", ":")) + "\n")

                total_pnl = position_update["total_pnl"]
                # Convert to float for logging (exchange sends as strings)
                realized_float = float(realized_pnl)
                unrealized_float = float(unrealized_pnl or 0)
                LOG.info(
                    "[account] position_pnl market=%s realized=%.2f unrealized=%.2f total=%.2f",
                    market, realized_float, unrealized_float, total_pnl
                )
            except Exception as exc:
                LOG.debug("[account] failed to log position update: %s", exc)

    def _compute_base_delta(self, fill: FillRecord) -> Decimal:
        size = Decimal(fill.size)
        acct_int = self._account_index_int

        def _to_int(value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value)
            except Exception:
                return None

        ask_account = _to_int(fill.raw.get("ask_account_id") or fill.raw.get("ask_account"))
        bid_account = _to_int(fill.raw.get("bid_account_id") or fill.raw.get("bid_account"))

        if acct_int is not None:
            if acct_int == ask_account:
                return -size
            if acct_int == bid_account:
                return size

        maker_is_ask = bool(fill.raw.get("is_maker_ask"))
        role = fill.role.lower()

        if role == "maker":
            return -size if maker_is_ask else size
        # role == taker or unknown
        return size if maker_is_ask else -size

    def _tracked_markets(self) -> list[str]:
        markets: set[str] = set()
        if self.market_filter:
            markets.update(self.market_filter)
        elif self.state and hasattr(self.state, "get_inventory"):
            try:
                inventory = self.state.get_inventory()
                if isinstance(inventory, dict):
                    markets.update(inventory.keys())
            except Exception:
                pass
        default_market = getattr(self, "default_market", None)
        if isinstance(default_market, str):
            markets.add(default_market)
        return list(markets)

    def _reset_position(self, market: str) -> None:
        self._set_inventory(market, Decimal("0"))

    def _set_inventory(self, market: str, value: Decimal) -> None:
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


