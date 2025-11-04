# core/main.py
import asyncio
import inspect
import logging
import os
import signal
import sys
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

# Optional imports (survive partial milestones)
try:
    from modules.funding_optimizer import FundingOptimizer
except Exception:  # noqa
    FundingOptimizer = None  # type: ignore

try:
    from modules.pair_selector import PairSelector
except Exception:  # noqa
    PairSelector = None  # type: ignore

try:
    from modules.maker_engine import MakerEngine
except Exception:  # noqa
    MakerEngine = None  # type: ignore

try:
    from modules.market_data_listener import MarketDataListener
except Exception:  # noqa
    MarketDataListener = None  # type: ignore

try:
    from modules.mock_metrics import MockMetrics, MockMetricsProvider
except Exception:  # noqa
    MockMetrics = None  # type: ignore
    MockMetricsProvider = None  # type: ignore

try:
    from core.state_store import StateStore
except Exception:  # noqa
    StateStore = None  # type: ignore

from modules.alert_manager import AlertManager
from modules.telemetry import Telemetry

# Compat shim from earlier step
try:
    from utils.compat import ConfigCompat
except Exception:
    # Minimal inline fallback if utils/compat.py is missing
    class ConfigCompat(SimpleNamespace):
        _warned: Dict[str, bool] = {}

        def __init__(
            self,
            base: Dict[str, Any],
            defaults: Dict[str, Any],
            aliases: Dict[str, str],
        ):
            super().__init__(**base)
            self.__dict__["_defaults"] = defaults
            self.__dict__["_aliases"] = aliases

        def __getattr__(self, name: str) -> Any:
            if name in self.__dict__:
                return self.__dict__[name]
            aliases = self.__dict__.get("_aliases", {})
            if name in aliases:
                return getattr(self, aliases[name])
            defaults = self.__dict__.get("_defaults", {})
            if name in defaults:
                return defaults[name]
            if not self._warned.get(name):
                logging.getLogger("compat").warning(
                    "[compat] optimizer config missing '%s' — using neutral default.",
                    name,
                )
                self._warned[name] = True
            return 0.0  # neutral default


APP_NAME = "lighter-bot"


def load_config() -> Dict[str, Any]:
    cfg_path = os.environ.get("LIGHTER_CONFIG", "config.yaml")
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f) or {}


def setup_logging():
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )
    for name in (
        "alert",
        "telemetry",
        "main",
        "listener",
        "maker",
        "optimizer",
        "selector",
        "compat",
    ):
        logging.getLogger(name).setLevel(level)


def _try_construct(cls, variants: List[Tuple[tuple, dict]]):
    last_exc = None
    for args, kwargs in variants:
        try:
            return cls(*args, **kwargs)
        except TypeError as e:
            last_exc = e
            continue
    if last_exc:
        raise last_exc
    return cls()  # pragma: no cover


class _FallbackMetrics:
    def __init__(self, markets: Optional[List[str]] = None):
        self.markets = markets or ["market:1", "market:2", "market:55", "market:99"]

    async def best_pairs(self, top_n: int = 2) -> List[str]:
        idx = int(time.time() // 15) % len(self.markets)
        ordered = self.markets[idx:] + self.markets[:idx]
        return ordered[: max(1, top_n)]


def _apr_to_8h(apr: float) -> float:
    return apr / 1095.0


class _DSAdapter:
    """
    Normalizes any data source to what FundingOptimizer expects:
      fetch_pair_metrics() -> List with attrs:
      market_id, funding_1h, funding_8h, funding_24h, open_interest, spread_bps, (optional symbol, score)
    """

    def __init__(self, source: Any, markets: Optional[List[str]] = None):
        self._src = source
        self._all_markets = markets or [
            "market:1",
            "market:2",
            "market:55",
            "market:99",
        ]
        self.LOG = logging.getLogger("optimizer")

    def _coerce_one(self, m: Any) -> Optional[SimpleNamespace]:
        if m is None:
            return None

        def get(obj, *names, default=None):
            for n in names:
                if isinstance(obj, dict) and n in obj:
                    return obj[n]
                if hasattr(obj, n):
                    return getattr(obj, n)
            return default

        market_id = get(m, "market_id", "market", "id")
        if not market_id or not isinstance(market_id, str):
            return None

        # accept any of these and derive others
        funding_8h = get(m, "funding_8h")
        funding_1h = get(m, "funding_1h")
        funding_24h = get(m, "funding_24h")
        funding_apr = get(m, "funding_apr", "apr", "fundingAPR")
        if funding_8h is None and isinstance(funding_apr, (int, float)):
            funding_8h = _apr_to_8h(float(funding_apr))
        if funding_apr is None and isinstance(funding_8h, (int, float)):
            funding_apr = float(funding_8h) * 1095.0
        if funding_1h is None and isinstance(funding_8h, (int, float)):
            funding_1h = float(funding_8h) / 8.0
        if funding_24h is None and isinstance(funding_8h, (int, float)):
            funding_24h = float(funding_8h) * 3.0
        if funding_apr is None and all(
            v is None for v in (funding_8h, funding_1h, funding_24h)
        ):
            funding_apr = 0.02  # fallback positive

        oi = get(m, "open_interest", "oi", default=0.0)
        spread_bps = get(m, "spread_bps", "spreadBps", default=12.0)
        symbol = get(m, "symbol")

        return SimpleNamespace(
            market_id=str(market_id),
            symbol=symbol if isinstance(symbol, str) else None,
            funding_1h=float(funding_1h) if funding_1h is not None else None,
            funding_8h=float(funding_8h) if funding_8h is not None else None,
            funding_24h=float(funding_24h) if funding_24h is not None else None,
            open_interest=float(oi) if oi is not None else None,
            spread_bps=float(spread_bps) if spread_bps is not None else None,
        )

    async def fetch_pair_metrics(self) -> List[SimpleNamespace]:
        # passthrough if provider already exposes the right call
        if hasattr(self._src, "fetch_pair_metrics"):
            fn = getattr(self._src, "fetch_pair_metrics")
            try:
                out = fn()
                if asyncio.iscoroutine(out):
                    out = await out
                if isinstance(out, list):
                    coerced = [self._coerce_one(x) for x in out]
                    return [c for c in coerced if c is not None]
            except Exception as e:
                self.LOG.debug("[ds] passthrough fetch_pair_metrics failed: %s", e)

        # otherwise fabricate plausible metrics favoring a rotating subset
        top: List[str] = []
        if hasattr(self._src, "best_pairs"):
            try:
                res = self._src.best_pairs(top_n=3)
                if asyncio.iscoroutine(res):
                    res = await res
                if isinstance(res, list):
                    top = [str(x) for x in res]
            except Exception as e:
                self.LOG.debug("[ds] best_pairs() failed: %s", e)

        if not top:
            idx = int(time.time() // 15) % len(self._all_markets)
            top = [
                self._all_markets[idx],
                self._all_markets[(idx + 1) % len(self._all_markets)],
            ]

        now = int(time.time())
        wob = ((now // 5) % 10) / 100.0
        out: List[SimpleNamespace] = []
        for i, m in enumerate(self._all_markets):
            is_top = m in top
            base_apr = 0.02 if is_top else -0.005
            apr = base_apr + wob - (0.001 * i)
            f8 = _apr_to_8h(apr)
            out.append(
                SimpleNamespace(
                    market_id=m,
                    symbol=None,
                    funding_1h=f8 / 8.0,
                    funding_8h=f8,
                    funding_24h=f8 * 3.0,
                    open_interest=1_000_000.0 if is_top else 250_000.0,
                    spread_bps=8.0 if is_top else 12.0,
                )
            )
        return out


class _MakerUpdater:
    def __init__(self, maker: Any, logger: logging.Logger):
        self.maker = maker
        self.LOG = logger

    # exact name the optimizer calls
    def update_active_pairs(self, market_ids: Sequence[str]) -> None:
        if not self.maker:
            self.LOG.info(
                "[updater] maker not present; ignoring pair update: %s",
                list(market_ids),
            )
            return
        if not market_ids:
            self.LOG.info("[updater] empty pair set; ignoring")
            return
        primary = list(market_ids)[0]
        try:
            prev = getattr(self.maker, "market", None)
            setattr(self.maker, "market", primary)
            self.LOG.info("[updater] switched maker market %s -> %s", prev, primary)
        except Exception as e:
            self.LOG.warning("[updater] failed to switch maker market: %s", e)

    # backward-compat if anything else calls this
    async def update_pairs(self, pairs: List[str]):
        self.update_active_pairs(pairs)


class _StateAdapter:
    """Wrap your StateStore to the minimal surface the optimizer wants."""

    def __init__(self, state: Any):
        self._state = state
        self._LOG = logging.getLogger("optimizer")

    # optimizer expects these names:
    def set_active_pairs(self, pairs: Sequence[str]) -> None:
        if hasattr(self._state, "set_active_pairs"):
            try:
                self._state.set_active_pairs(list(pairs))
                return
            except Exception:
                pass
        # Soft fallback: store on self for visibility
        setattr(self._state, "_active_pairs", list(pairs))

    def get_active_pairs(self) -> List[str]:
        if hasattr(self._state, "get_active_pairs"):
            try:
                return list(self._state.get_active_pairs())
            except Exception:
                pass
        return list(getattr(self._state, "_active_pairs", []))

    def set_pair_metrics(self, metrics: Dict[str, Any]) -> None:
        if hasattr(self._state, "set_pair_metrics"):
            try:
                self._state.set_pair_metrics(metrics)
                return
            except Exception:
                pass
        setattr(self._state, "_pair_metrics", metrics)

    def now(self) -> float:
        if hasattr(self._state, "now"):
            try:
                return float(self._state.now())
            except Exception:
                pass
        return time.time()


def _opt_cfg_from_dict(root_cfg: Dict[str, Any]) -> ConfigCompat:
    """
    Build attribute-style optimizer config matching your OptimizerConfig dataclass.
    Also supports common aliases used in earlier iterations.
    """
    src = (
        (root_cfg.get("optimizer") or {})
        if isinstance(root_cfg.get("optimizer"), dict)
        else {}
    )

    # Defaults copied from modules/funding_optimizer.py::OptimizerConfig
    defaults: Dict[str, Any] = {
        "scan_interval_s": 30,
        "top_n": 3,
        "min_open_interest": 0.0,
        "max_spread_bps": 25.0,
        "w_funding": 1.0,
        "w_oi": 0.2,
        "spread_bps_penalty": 0.02,
        "min_dwell_s": 120,
        "hysteresis_score_margin": 0.05,
        "max_switches_per_hour": 12,
    }

    # merge user overrides
    merged = {**defaults, **src}

    # aliases supported
    aliases = {
        # weight/penalty aliases
        "apr_weight": "w_funding",
        "oi_weight": "w_oi",
        "w_spread_penalty": "spread_bps_penalty",
        # thresholds/stability aliases
        "min_oi": "min_open_interest",
        "dwell_seconds": "min_dwell_s",
        "switches_per_hour": "max_switches_per_hour",
        # historical alias we used earlier
        "hysteresis": "hysteresis_score_margin",
    }

    # coerce numeric types where relevant
    ints = {"scan_interval_s", "top_n", "min_dwell_s", "max_switches_per_hour"}
    floats = {
        "min_open_interest",
        "max_spread_bps",
        "w_funding",
        "w_oi",
        "spread_bps_penalty",
        "hysteresis_score_margin",
    }
    for k in list(merged.keys()):
        try:
            if k in ints:
                merged[k] = int(merged[k])
            elif k in floats:
                merged[k] = float(merged[k])
        except Exception:
            merged[k] = defaults.get(k, merged[k])

    return ConfigCompat(merged, defaults, aliases)


def fire_and_forget(coro):  # type: ignore
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        pass


async def main():
    setup_logging()
    cfg = load_config()
    app = (cfg.get("app") or {}).get("name", APP_NAME)

    # --- Alerts & Telemetry ---
    alerts_cfg = cfg.get("alerts") or {}
    telemetry_cfg = cfg.get("telemetry") or {}

    alert_mgr = AlertManager(
        webhook_url=alerts_cfg.get("discord_webhook_url"),
        enabled=bool(alerts_cfg.get("enabled", True)),
        app_name=app,
    )
    telemetry = Telemetry(
        enabled=bool(telemetry_cfg.get("enabled", False)),
        port=int(telemetry_cfg.get("port", 9100)),
    )
    telemetry.start()

    start_ts = time.time()
    telemetry.set_gauge("app_start_ts", start_ts)
    fire_and_forget(
        alert_mgr.info("Startup", f"{app} starting (M7 Telemetry & Alerts).")
    )

    loop = asyncio.get_running_loop()

    def handle_exception(loop, context):
        msg = context.get("message")
        exc = context.get("exception")
        loop.default_exception_handler(context)
        fire_and_forget(
            alert_mgr.error(
                "Unhandled exception",
                message=str(msg) if msg else repr(exc),
                fields=(
                    {"type": type(exc).__name__ if exc else "unknown"} if exc else None
                ),
            )
        )

    loop.set_exception_handler(handle_exception)

    # Graceful shutdown
    stop_event = asyncio.Event()
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, stop_event.set)
        except NotImplementedError:
            pass

    # --- Core components ---
    state = StateStore() if StateStore else SimpleNamespace()
    state_adapter = _StateAdapter(state)

    listener = None
    if MarketDataListener:
        listener = _try_construct(
            MarketDataListener,
            [
                (
                    (),
                    {
                        "config": cfg,
                        "state": state,
                        "alert_manager": alert_mgr,
                        "telemetry": telemetry,
                    },
                ),
                ((), {"config": cfg, "state": state}),
                ((cfg, state), {}),
                ((cfg,), {}),
            ],
        )

    maker = None
    if MakerEngine:
        maker = _try_construct(
            MakerEngine,
            [
                (
                    (),
                    {
                        "config": cfg,
                        "state": state,
                        "alert_manager": alert_mgr,
                        "telemetry": telemetry,
                    },
                ),
                ((), {"config": cfg, "state": state}),
                ((cfg, state), {}),
                ((state, cfg), {}),
                ((state,), {}),
                ((), {}),
            ],
        )

    # Data source -> adapter
    raw_ds = None
    if MockMetricsProvider:
        try:
            raw_ds = MockMetricsProvider()
        except Exception:
            raw_ds = None
    if not raw_ds and MockMetrics:
        try:
            raw_ds = MockMetrics()
        except Exception:
            raw_ds = None
    if not raw_ds:
        raw_ds = _FallbackMetrics()
    data_source = _DSAdapter(raw_ds)

    optimizer = None
    if FundingOptimizer:
        opt_cfg_ns = _opt_cfg_from_dict(cfg)
        maker_updater = _MakerUpdater(maker, logging.getLogger("optimizer"))

        # Prefer the (data_source, state, maker_updater, cfg) signature
        sig = None
        try:
            sig = inspect.signature(FundingOptimizer)
        except Exception:
            sig = None

        if sig and len(sig.parameters) >= 4:
            try:
                optimizer = FundingOptimizer(data_source, state_adapter, maker_updater, opt_cfg_ns)  # type: ignore
            except TypeError:
                optimizer = _try_construct(
                    FundingOptimizer,
                    [
                        (
                            (),
                            {
                                "config": cfg,
                                "state": state,
                                "alert_manager": alert_mgr,
                                "telemetry": telemetry,
                            },
                        ),
                        ((), {"config": cfg, "state": state}),
                        ((cfg, state), {}),
                        ((state, cfg), {}),
                        ((state,), {}),
                        ((), {}),
                    ],
                )
        else:
            optimizer = _try_construct(
                FundingOptimizer,
                [
                    (
                        (),
                        {
                            "config": cfg,
                            "state": state,
                            "alert_manager": alert_mgr,
                            "telemetry": telemetry,
                        },
                    ),
                    ((), {"config": cfg, "state": state}),
                    ((cfg, state), {}),
                    ((state, cfg), {}),
                    ((state,), {}),
                    ((), {}),
                ],
            )

    selector = None
    if PairSelector:
        selector = _try_construct(
            PairSelector,
            [
                (
                    (),
                    {
                        "config": cfg,
                        "state": state,
                        "alert_manager": alert_mgr,
                        "telemetry": telemetry,
                    },
                ),
                ((), {"config": cfg, "state": state}),
                ((cfg, state), {}),
                ((state, cfg), {}),
                ((state,), {}),
                ((), {}),
            ],
        )

    tasks: List[asyncio.Task] = []

    async def periodic_core_metrics():
        while not stop_event.is_set():
            telemetry.set_gauge("uptime_seconds", max(0.0, time.time() - start_ts))
            await asyncio.sleep(5.0)

    tasks.append(asyncio.create_task(periodic_core_metrics(), name="metrics"))

    async def run_component(name: str, comp):
        if not comp:
            return
        logging.getLogger("main").info("[%s] starting.", name)

        if hasattr(comp, "run") and asyncio.iscoroutinefunction(comp.run):
            await comp.run()
            return
        if hasattr(comp, "start") and asyncio.iscoroutinefunction(comp.start):
            await comp.start()
            return
        if hasattr(comp, "start") and callable(comp.start):
            result = comp.start()
            if inspect.iscoroutine(result):
                await result
            elif isinstance(result, asyncio.Task):
                await result
            else:
                logging.getLogger("main").info("[%s] started (self-managed).", name)
                return
        logging.getLogger("main").info(
            "[%s] no run/start; assuming self-managed.", name
        )

    if listener:
        tasks.append(asyncio.create_task(run_component("listener", listener)))
    if optimizer:
        tasks.append(asyncio.create_task(run_component("optimizer", optimizer)))
    if selector:
        tasks.append(asyncio.create_task(run_component("selector", selector)))
    if maker:
        tasks.append(asyncio.create_task(run_component("maker", maker)))

    # --- Watchdogs (M7) ---
    wd_cfg = cfg.get("watchdogs") or {}
    ws_stale_sec = int(wd_cfg.get("ws_stale_seconds", 30))
    quote_stale_sec = int(wd_cfg.get("quote_stale_seconds", 20))
    resend_every_sec = int(wd_cfg.get("reminder_every_seconds", 300))
    last_ws_alert = 0.0
    last_quote_alert = 0.0

    async def watchdogs():
        nonlocal last_ws_alert, last_quote_alert
        logging.getLogger("main").info(
            "[main] watchdogs enabled. ws_stale=%ss quote_stale=%ss",
            ws_stale_sec,
            quote_stale_sec,
        )
        while not stop_event.is_set():
            now = time.time()
            _, _, hbs = telemetry.metrics.snapshot()
            ws_last = hbs.get("ws")
            qt_last = hbs.get("quote")

            if ws_last:
                ws_age = now - ws_last
                if ws_age > ws_stale_sec and (now - last_ws_alert) > resend_every_sec:
                    last_ws_alert = now
                    fire_and_forget(
                        alert_mgr.warning(
                            "WebSocket appears stale",
                            message=f"No WS frames for {int(ws_age)}s.",
                            fields={"ws_last_ts": ws_last, "ws_age_s": int(ws_age)},
                        )
                    )

            if qt_last:
                q_age = now - qt_last
                if (
                    q_age > quote_stale_sec
                    and (now - last_quote_alert) > resend_every_sec
                ):
                    last_quote_alert = now
                    fire_and_forget(
                        alert_mgr.warning(
                            "Maker quotes stale",
                            message=f"No quotes emitted for {int(q_age)}s.",
                            fields={
                                "quote_last_ts": qt_last,
                                "quote_age_s": int(q_age),
                            },
                        )
                    )
            await asyncio.sleep(2.0)

    tasks.append(asyncio.create_task(watchdogs(), name="watchdogs"))

    logging.getLogger("main").info("Starting %s (M7 Telemetry & Alerts)...", app)
    try:
        await stop_event.wait()
    finally:
        logging.getLogger("main").info("Shutting down...")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        telemetry.set_gauge("shutdown_ts", time.time())
        fire_and_forget(alert_mgr.info("Shutdown", f"{app} stopped."))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
