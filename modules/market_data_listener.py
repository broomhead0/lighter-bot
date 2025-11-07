# modules/market_data_listener.py
import asyncio
import json
import logging
import os
import random
import time
from typing import Any, Dict

LOG = logging.getLogger("listener")

try:
    import websockets  # type: ignore
except Exception:  # pragma: no cover
    websockets = None  # type: ignore


class MarketDataListener:
    """
    Market stats listener with WS + synthetic fallback.

    M7:
      - telemetry.touch('ws') on every frame/tick so watchdogs work
      - raw capture to logs/ws_raw.jsonl when capture.write_raw: true
      - NEW: after N consecutive WS connection failures, auto-fall back to synthetic
    """

    def __init__(
        self,
        config: Dict[str, Any],
        state: Any = None,
        alert_manager: Any = None,  # M7 optional
        telemetry: Any = None,  # M7 optional
    ):
        self.cfg = config or {}
        self.state = state
        self.alerts = alert_manager
        self.telemetry = telemetry

        app_cfg = (
            (self.cfg.get("app") or {}) if isinstance(self.cfg.get("app"), dict) else {}
        )
        self.app_name = app_cfg.get("name", "lighter-bot")

        ws_cfg = (
            (self.cfg.get("ws") or {}) if isinstance(self.cfg.get("ws"), dict) else {}
        )
        self.ws_url = ws_cfg.get("url") or os.environ.get("WS_URL")
        self.ws_fail_fallback = bool(ws_cfg.get("fallback_on_fail", True))
        self.ws_max_failures = int(ws_cfg.get("max_failures", 3))

        channels_cfg = ws_cfg.get("channels")
        if isinstance(channels_cfg, list) and channels_cfg:
            self.ws_channels = [str(ch) for ch in channels_cfg]
        elif isinstance(channels_cfg, str) and channels_cfg.strip():
            self.ws_channels = [channels_cfg.strip()]
        else:
            # default: subscribe to all market stats
            self.ws_channels = ["market_stats/all"]

        self.ws_auth_token = ws_cfg.get("auth_token") or os.environ.get("WS_AUTH_TOKEN")
        self.ws_mid_log_interval = float(ws_cfg.get("log_mid_interval_s", 1.0))

        maker_cfg = self.cfg.get("maker") or {}
        maker_pairs = maker_cfg.get("pairs") or maker_cfg.get("pair")
        if isinstance(maker_pairs, str):
            maker_pairs = [maker_pairs]
        if isinstance(maker_pairs, (list, tuple)):
            derived = []
            for pair in maker_pairs:
                if isinstance(pair, str) and pair.startswith("market:"):
                    suffix = pair.split(":", 1)[1]
                    if suffix:
                        channel = f"market_stats/{suffix}"
                        if channel not in self.ws_channels and channel not in derived:
                            derived.append(channel)
            if derived:
                self.ws_channels.extend(derived)
                LOG.info("[listener] auto-subscribe channels from maker config: %s", derived)

        self._ws_subscribed_channels: set[str] = set()
        self._last_mid_log_ts: float = 0.0

        cap_cfg = (
            (self.cfg.get("capture") or {})
            if isinstance(self.cfg.get("capture"), dict)
            else {}
        )
        self.capture_raw = bool(cap_cfg.get("write_raw", False))
        self.capture_path = cap_cfg.get(
            "raw_path", os.path.join("logs", "ws_raw.jsonl")
        )

        syn_cfg = (
            (self.cfg.get("synthetic") or {})
            if isinstance(self.cfg.get("synthetic"), dict)
            else {}
        )
        self.synthetic_market = syn_cfg.get("market", "market:1")
        self.synthetic_start = float(syn_cfg.get("mid_start", 107000.0))
        self.synthetic_step = float(syn_cfg.get("tick_step", 5.0))
        self.synthetic_jitter = float(syn_cfg.get("tick_jitter", 2.0))
        self.synthetic_interval = float(syn_cfg.get("interval_seconds", 1.0))

        self._stop = asyncio.Event()
        self._consecutive_failures = 0

        if self.capture_raw:
            try:
                os.makedirs(os.path.dirname(self.capture_path), exist_ok=True)
            except Exception:
                pass

    async def run(self):
        """
        Run until cancelled. Chooses WS or synthetic; falls back after repeated failures.
        """
        # No WS configured or lib missing -> synthetic
        if not (self.ws_url and websockets):
            LOG.info(
                "[feeder] No usable WS (url=%s websockets=%s); starting SyntheticMidFeeder for %s from %s",
                self.ws_url,
                bool(websockets),
                self.synthetic_market,
                self.synthetic_start,
            )
            await self._run_synthetic()
            return

        while not self._stop.is_set():
            try:
                await self._run_ws_once()
                self._consecutive_failures = 0  # reset on success
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._consecutive_failures += 1
                LOG.warning(
                    "[listener] socket error on %s: %s (fail #%d)",
                    self.ws_url,
                    e,
                    self._consecutive_failures,
                )
                await self._alert("warning", "WS disconnected", str(e))
                if (
                    self.ws_fail_fallback
                    and self._consecutive_failures >= self.ws_max_failures
                ):
                    LOG.warning(
                        "[listener] max failures reached; falling back to synthetic feed."
                    )
                    await self._alert(
                        "warning",
                        "WS fallback to synthetic",
                        f"failures={self._consecutive_failures}",
                    )
                    await self._run_synthetic()
                    return
                await asyncio.sleep(2.0)

    async def stop(self):
        self._stop.set()

    # ------------------------- WS mode -------------------------

    async def _run_ws_once(self):
        assert websockets is not None  # guarded by caller
        LOG.info("[listener] connecting %s", self.ws_url)
        async with websockets.connect(
            self.ws_url,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=10,
        ) as ws:  # type: ignore
            await self._alert("info", "WS connected", self.ws_url)
            self._ws_subscribed_channels.clear()
            await self._send_ws_subscriptions(ws)

            while not self._stop.is_set():
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=60)  # type: ignore
                    ts = time.time()
                    if isinstance(raw_msg, (bytes, bytearray)):
                        raw_msg = raw_msg.decode("utf-8", "ignore")
                    LOG.debug("[listener] received message: %s", raw_msg[:200] if len(raw_msg) > 200 else raw_msg)
                    self._touch_ws()
                    self._capture_raw(raw_msg, ts)

                    try:
                        obj = json.loads(raw_msg) if raw_msg else {}
                    except Exception:
                        LOG.debug("[listener] unable to parse frame as JSON")
                        continue

                    msg_type = obj.get("type")
                    if msg_type == "connected":
                        await self._send_ws_subscriptions(ws)
                        continue
                    if msg_type == "ping":
                        try:
                            await ws.send(json.dumps({"type": "pong"}))
                            LOG.debug("[listener] sent pong response")
                        except Exception as e:
                            LOG.debug("[listener] failed to send pong: %s", e)
                        continue

                    self._route_frame_obj(obj, ts)
                except asyncio.TimeoutError:
                    LOG.warning("[listener] no message received in 60s, connection may be idle")
                    self._touch_ws()
                    continue

    # --------------------- Synthetic mode ---------------------

    async def _run_synthetic(self):
        mid = self.synthetic_start
        t = 0.0
        while not self._stop.is_set():
            drift = self.synthetic_step * (
                random.random() - 0.5
            ) + self.synthetic_jitter * random.uniform(-1, 1)
            wave = 3.0 * self.synthetic_step * (0.5 * (1 + math_sin_safe(t)))
            mid = max(1.0, mid + drift + wave)

            frame = {
                "channel": "market_stats:all",
                "type": "update/market_stats",
                "ts": time.time(),
                "data": [{"market": self.synthetic_market, "mid": mid}],
            }
            encoded = json.dumps(frame)
            self._touch_ws()
            self._capture_raw(encoded, frame["ts"])
            self._route_frame(encoded, frame["ts"])
            await asyncio.sleep(self.synthetic_interval)
            t += self.synthetic_interval

    # ----------------------- Helpers --------------------------

    def _touch_ws(self):
        if getattr(self, "telemetry", None):
            try:
                self.telemetry.touch("ws")
            except Exception:
                pass

    def _capture_raw(self, raw: str, ts: float):
        if not self.capture_raw:
            return
        try:
            with open(self.capture_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": ts, "raw": raw}) + "\n")
        except Exception as e:
            LOG.debug("[listener] capture failed: %s", e)

    def _route_frame(self, raw: str, ts: float):
        try:
            obj = json.loads(raw) if raw else {}
        except Exception:
            LOG.debug("[listener] non-json frame")
            return
        self._route_frame_obj(obj, ts)

    async def _send_ws_subscriptions(self, ws) -> None:
        for channel in self.ws_channels:
            if channel in self._ws_subscribed_channels:
                continue
            payload = {"type": "subscribe", "channel": channel}
            if self.ws_auth_token:
                payload["auth"] = self.ws_auth_token
            try:
                await ws.send(json.dumps(payload))
                LOG.info("[listener] sent subscription: %s", channel)
                self._ws_subscribed_channels.add(channel)
            except Exception as e:
                LOG.warning("[listener] failed to subscribe %s: %s", channel, e)

    def _route_frame_obj(self, obj: Dict[str, Any], ts: float):
        if not isinstance(obj, dict):
            return

        channel = (obj.get("channel") or "")
        msg_type = (obj.get("type") or "")

        if msg_type.endswith("market_stats"):
            handled = False

            data_list = obj.get("data")
            if isinstance(data_list, list):
                for item in data_list:
                    if not isinstance(item, dict):
                        continue
                    market_id = item.get("market")
                    mid = item.get("mid")
                    handled = self._handle_market_stats_entry(market_id, mid, ts) or handled

            market_stats_obj = obj.get("market_stats")
            if isinstance(market_stats_obj, dict):
                market_id = market_stats_obj.get("market_id")
                mark_price = market_stats_obj.get("mark_price")
                handled = self._handle_market_stats_entry(market_id, mark_price, ts) or handled

            if not handled:
                LOG.debug("[listener] market_stats frame without usable mids: %s", obj)


    def _handle_market_stats_entry(self, market_id, mid_value, ts: float) -> bool:
        formatted_market = self._format_market_id(market_id)
        if not formatted_market:
            return False

        mid = self._parse_mid_value(mid_value)
        if mid is None:
            return False

        if self.state and hasattr(self.state, "update_mid"):
            try:
                self.state.update_mid(formatted_market, float(mid))
            except Exception as e:
                LOG.debug("[listener] state.update_mid failed: %s", e)
                return False

        should_log = (
            self.ws_mid_log_interval <= 0
            or (ts - self._last_mid_log_ts) >= self.ws_mid_log_interval
            or self._last_mid_log_ts == 0.0
        )

        if should_log:
            self._last_mid_log_ts = ts
            LOG.info("[router] mid updated %s -> %.6f", formatted_market, float(mid))
        else:
            LOG.debug("[router] mid updated %s -> %.6f", formatted_market, float(mid))
        return True

    def _format_market_id(self, market_id):
        if isinstance(market_id, str) and market_id:
            return market_id
        if isinstance(market_id, int):
            return f"market:{market_id}"
        if isinstance(market_id, float) and market_id.is_integer():
            return f"market:{int(market_id)}"
        return None

    def _parse_mid_value(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None


    async def _alert(self, level: str, title: str, message: str = ""):
        if getattr(self, "alerts", None) and hasattr(self.alerts, level):
            try:
                await getattr(self.alerts, level)(title, message)
            except Exception:
                pass


def math_sin_safe(x: float) -> float:
    try:
        import math

        return math.sin(x)
    except Exception:
        return 0.0
