# modules/maker_engine.py
import asyncio
import logging
import math
import random
import time
from typing import Any, Dict, Optional, Tuple

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
    ):
        self.cfg = config or {}
        self.state = state
        self.alerts = alert_manager
        self.telemetry = telemetry

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
        # Fallback: synthetic drifting mid so we can demonstrate quotes even without WS
        return self._synthetic_mid()

    def _compute_quotes(self, mid: float) -> Tuple[float, float, float]:
        jitter = random.uniform(-self.randomize_bps, self.randomize_bps)
        bps = max(1e-6, self.spread_bps + jitter)
        half = (bps / 20000.0) * mid  # half-spread in price units
        bid = max(0.0000001, mid - half)
        ask = mid + half
        return bid, ask, bps

    async def _post_quotes(self, bid: float, ask: float, size: float):
        """
        Dry-run placeholder. Replace with REST maker v1 if you have it:
        - post-only limit bid @ bid
        - post-only limit ask @ ask
        - cancel/replace on refresh
        """
        # No-op; just pretend we posted.
        await asyncio.sleep(0)

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
