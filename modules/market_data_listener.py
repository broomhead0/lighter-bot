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
        async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:  # type: ignore
            await self._alert("info", "WS connected", self.ws_url)

            # Try to subscribe to market_stats channel
            # Lighter WebSocket may require subscription message
            try:
                subscribe_msg = json.dumps({
                    "type": "subscribe",
                    "channel": "market_stats:all"
                })
                await ws.send(subscribe_msg)
                LOG.info("[listener] sent subscription: market_stats:all")
            except Exception as e:
                LOG.debug("[listener] subscription attempt failed (may not be required): %s", e)

            while not self._stop.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=60)  # type: ignore
                    ts = time.time()
                    LOG.debug("[listener] received message: %s", msg[:200] if len(msg) > 200 else msg)
                    self._touch_ws()
                    self._capture_raw(msg, ts)
                    self._route_frame(msg, ts)
                except asyncio.TimeoutError:
                    LOG.warning("[listener] no message received in 60s, connection may be idle")
                    # Touch to keep connection alive
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
            obj = json.loads(raw)
        except Exception:
            LOG.debug("[listener] non-json frame")
            return

        if not isinstance(obj, dict):
            return
        ch = obj.get("channel")
        typ = obj.get("type")
        if ch == "market_stats:all" and (typ or "").endswith("market_stats"):
            updates = obj.get("data") or []
            for item in updates:
                market_id = item.get("market")
                mid = item.get("mid")
                if market_id and isinstance(mid, (int, float)):
                    if self.state and hasattr(self.state, "update_mid"):
                        try:
                            self.state.update_mid(market_id, float(mid), ts)
                        except Exception as e:
                            LOG.debug("[listener] state.update_mid failed: %s", e)
                    LOG.info("[router] mid updated %s -> %.6f", market_id, float(mid))

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
