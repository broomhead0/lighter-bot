# core/main.py
import asyncio
import inspect
import json
import logging
import os
import signal
import sys
import time
from decimal import Decimal
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

try:
    from core.message_router import MessageRouter
except Exception:  # noqa
    MessageRouter = None  # type: ignore

try:
    from scripts.replay_sim import ReplaySimulator
except Exception:  # noqa
    ReplaySimulator = None  # type: ignore

try:
    from modules.chaos_injector import ChaosInjector
except Exception:  # noqa
    ChaosInjector = None  # type: ignore

try:
    from modules.self_trade_guard import SelfTradeGuard
except Exception:  # noqa
    SelfTradeGuard = None  # type: ignore

try:
    from modules.account_listener import AccountListener
except Exception:  # noqa
    AccountListener = None  # type: ignore

from core.trading_client import TradingClient, TradingConfig

try:
    from modules.hedger import Hedger
except Exception:  # noqa
    Hedger = None  # type: ignore

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
        cfg = yaml.safe_load(f) or {}
    return _apply_env_overrides(cfg)


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


CONFIG_LOG = logging.getLogger("config")


def _apply_env_overrides(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Overlay environment variable values onto the YAML config."""
    specs: List[Tuple[Tuple[str, ...], str, str]] = [
        (("app", "log_level"), "APP_LOG_LEVEL", "str"),
        (("app", "name"), "APP_NAME", "str"),
        (("ws", "url"), "WS_URL", "str"),
        (("ws", "auth_token"), "WS_AUTH_TOKEN", "str"),
        (("ws", "log_mid_interval_s"), "WS_LOG_MID_INTERVAL_S", "float"),
        (("api", "base_url"), "API_BASE_URL", "str"),
        (("api", "key"), "API_KEY_PRIVATE_KEY", "str"),
        (("api", "account_index"), "ACCOUNT_INDEX", "int"),
        (("api", "api_key_index"), "API_KEY_INDEX", "int"),
        (("api", "max_api_key_index"), "MAX_API_KEY_INDEX", "int"),
        (("api", "nonce_management"), "NONCE_MANAGEMENT", "str"),
        (("maker", "dry_run"), "MAKER_DRY_RUN", "bool"),
        (("maker", "pair"), "MAKER_PAIR", "str"),
        (("maker", "size"), "MAKER_SIZE", "float"),
        (("maker", "spread_bps"), "MAKER_SPREAD_BPS", "float"),
        (("maker", "refresh_seconds"), "MAKER_REFRESH_SECONDS", "float"),
        (("maker", "randomize_bps"), "MAKER_RANDOMIZE_BPS", "float"),
        (("maker", "price_scale"), "MAKER_PRICE_SCALE", "float"),
        (("maker", "size_scale"), "MAKER_SIZE_SCALE", "float"),
        (("maker", "limits", "max_cancels"), "MAKER_LIMITS_MAX_CANCELS", "int"),
        (("maker", "limits", "max_latency_ms"), "MAKER_LIMITS_MAX_LATENCY_MS", "int"),
        (("hedger", "enabled"), "HEDGER_ENABLED", "bool"),
        (("hedger", "dry_run"), "HEDGER_DRY_RUN", "bool"),
        (("hedger", "market"), "HEDGER_MARKET", "str"),
        (("hedger", "trigger_units"), "HEDGER_TRIGGER_UNITS", "float"),
        (("hedger", "trigger_notional"), "HEDGER_TRIGGER_NOTIONAL", "float"),
        (("hedger", "target_units"), "HEDGER_TARGET_UNITS", "float"),
        (("hedger", "max_clip_units"), "HEDGER_MAX_CLIP_UNITS", "float"),
        (("hedger", "price_offset_bps"), "HEDGER_PRICE_OFFSET_BPS", "float"),
        (("hedger", "poll_interval_seconds"), "HEDGER_POLL_INTERVAL_SECONDS", "float"),
        (("hedger", "cooldown_seconds"), "HEDGER_COOLDOWN_SECONDS", "float"),
        (("hedger", "max_attempts"), "HEDGER_MAX_ATTEMPTS", "int"),
        (("hedger", "retry_backoff_seconds"), "HEDGER_RETRY_BACKOFF_SECONDS", "float"),
        (("hedger", "trigger_notional"), "HEDGER_TRIGGER_NOTIONAL", "float"),
        (("fees", "maker_actual_rate"), "FEES_MAKER_ACTUAL_RATE", "float"),
        (("fees", "taker_actual_rate"), "FEES_TAKER_ACTUAL_RATE", "float"),
        (("fees", "maker_premium_rate"), "FEES_MAKER_PREMIUM_RATE", "float"),
        (("fees", "taker_premium_rate"), "FEES_TAKER_PREMIUM_RATE", "float"),
        (("alerts", "enabled"), "ALERTS_ENABLED", "bool"),
        (("alerts", "discord_webhook_url"), "DISCORD_WEBHOOK", "str"),
        (("telemetry", "enabled"), "TELEMETRY_ENABLED", "bool"),
        (("telemetry", "port"), "TELEMETRY_PORT", "int"),
        (("watchdogs", "ws_stale_seconds"), "WATCHDOG_WS_STALE_SECONDS", "int"),
        (("watchdogs", "quote_stale_seconds"), "WATCHDOG_QUOTE_STALE_SECONDS", "int"),
        (("watchdogs", "reminder_every_seconds"), "WATCHDOG_REMINDER_EVERY_SECONDS", "int"),
        (("guard", "price_band_bps"), "GUARD_PRICE_BAND_BPS", "float"),
        (("guard", "crossed_book_protection"), "GUARD_CROSSED_BOOK_PROTECTION", "bool"),
        (("guard", "max_position_units"), "GUARD_MAX_POSITION_UNITS", "float"),
        (("guard", "max_inventory_notional"), "GUARD_MAX_INVENTORY_NOTIONAL", "float"),
        (("guard", "kill_on_crossed_book"), "GUARD_KILL_ON_CROSSED_BOOK", "bool"),
        (("guard", "kill_on_inventory_breach"), "GUARD_KILL_ON_INVENTORY_BREACH", "bool"),
        (("guard", "backoff_seconds_on_block"), "GUARD_BACKOFF_SECONDS_ON_BLOCK", "int"),
        (("replay", "enabled"), "REPLAY_ENABLED", "bool"),
        (("chaos", "enabled"), "CHAOS_ENABLED", "bool"),
        (("optimizer", "enabled"), "OPTIMIZER_ENABLED", "bool"),
        (("optimizer", "top_n"), "OPTIMIZER_TOP_N", "int"),
        (("optimizer", "scan_interval_s"), "OPTIMIZER_SCAN_INTERVAL_S", "int"),
        (("optimizer", "min_dwell_s"), "OPTIMIZER_MIN_DWELL_S", "int"),
    ]

    for path, env_name, kind in specs:
        raw = os.environ.get(env_name)
        if raw is None or raw == "":
            continue
        try:
            coerced = _coerce_env_value(raw, kind)
        except ValueError as exc:
            CONFIG_LOG.warning(
                "[config] unable to coerce %s for %s (%s): %s",
                raw,
                env_name,
                "->".join(path),
                exc,
            )
            continue
        _set_nested(cfg, path, coerced)

    return cfg


def _set_nested(cfg: Dict[str, Any], path: Tuple[str, ...], value: Any) -> None:
    cur = cfg
    for key in path[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    cur[path[-1]] = value


def _coerce_env_value(raw: str, kind: str) -> Any:
    if kind == "str":
        return raw
    if kind == "int":
        return int(raw)
    if kind == "float":
        return float(raw)
    if kind == "bool":
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        raise ValueError("expected boolean value")
    return raw


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
        "enabled": True,
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


def _build_trading_config(
    api_cfg: Dict[str, Any],
    maker_cfg: Optional[Dict[str, Any]],
) -> Optional[TradingConfig]:
    base_url = api_cfg.get("base_url")
    private_key = api_cfg.get("private_key") or api_cfg.get("key")
    account_index = api_cfg.get("account_index")
    api_key_index = api_cfg.get("api_key_index")

    if not (base_url and private_key and account_index is not None and api_key_index is not None):
        return None

    maker_cfg = maker_cfg or {}
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
        logging.getLogger("trading").warning("[main] invalid trading config: %s", exc)
        return None


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
    shared_trading_client: Optional[TradingClient] = None
    api_cfg = cfg.get("api") or {}
    maker_cfg = cfg.get("maker") or {}
    trading_cfg = _build_trading_config(api_cfg, maker_cfg)
    if trading_cfg:
        try:
            shared_trading_client = TradingClient(trading_cfg)
            logging.getLogger("main").info("[main] shared trading client initialized")
        except Exception as exc:
            shared_trading_client = None
            logging.getLogger("main").warning("[main] shared trading client unavailable: %s", exc)

    state_adapter = _StateAdapter(state)

    # --- Chaos injector (M8) ---
    chaos = None
    if ChaosInjector:
        try:
            chaos = ChaosInjector(cfg)
            if chaos.enabled:
                logging.getLogger("main").info("[main] CHAOS INJECTOR enabled")
        except Exception as e:
            logging.getLogger("main").warning(
                "[main] failed to initialize chaos injector: %s", e
            )

    # --- Replay mode (M8) ---
    replay_cfg = cfg.get("replay") or {}
    replay_enabled = bool(replay_cfg.get("enabled", False))
    replay_sim = None

    if replay_enabled:
        if not ReplaySimulator or not MessageRouter:
            logging.getLogger("main").error(
                "[main] replay enabled but ReplaySimulator/MessageRouter not available"
            )
            sys.exit(1)

        replay_path = replay_cfg.get("path", "logs/ws_raw.jsonl")
        replay_speed = float(replay_cfg.get("speed", 1.0))
        replay_market_filter = replay_cfg.get("market_filter")  # None or list

        # Create router for replay
        market_id_map = cfg.get("market_id_map") or {}
        router = MessageRouter(state, market_id_map=market_id_map)

        # Create simulator
        replay_sim = ReplaySimulator(
            path=replay_path,
            router=router.route,
            speed=replay_speed,
            market_filter=replay_market_filter,
            telemetry=telemetry,
            chaos_injector=chaos,
        )

        logging.getLogger("main").info(
            "[main] REPLAY MODE enabled: path=%s speed=%.2fx filter=%s",
            replay_path,
            replay_speed,
            replay_market_filter,
        )
        # Disable live listener in replay mode
        listener = None
    else:
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

    # SelfTradeGuard (critical safety feature)
    self_trade_guard = None
    if SelfTradeGuard:
        guard_cfg = (cfg.get("guard") or {}) if isinstance(cfg.get("guard"), dict) else {}
        try:
            self_trade_guard = SelfTradeGuard(state=state, cfg=guard_cfg)
            logging.getLogger("main").info("[main] SelfTradeGuard initialized")
        except Exception as e:
            logging.getLogger("main").warning(f"[main] SelfTradeGuard init failed: {e}")

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
                        "chaos_injector": chaos,
                        "guard": self_trade_guard,
                        "trading_client": shared_trading_client,
                    },
                ),
                ((), {"config": cfg, "state": state}),
                ((cfg, state), {}),
                ((state, cfg), {}),
                ((state,), {}),
                ((), {}),
            ],
        )

    hedger = None
    if Hedger:
        hedger_cfg = cfg.get("hedger") or {}
        if bool(hedger_cfg.get("enabled", False)):
            try:
                hedger = Hedger(
                    config=cfg,
                    state=state,
                    telemetry=telemetry,
                    alert_manager=alert_mgr,
                    trading_client=shared_trading_client,
                )
                logging.getLogger("main").info("[main] Hedger initialized")
            except Exception as exc:
                logging.getLogger("main").warning("[main] Hedger init failed: %s", exc)

    account_listener = None
    if AccountListener:
        acct_cfg = cfg.get("account_listener") or {}
        enabled = bool(acct_cfg.get("enabled", True))
        if enabled:
            merged_cfg = dict(acct_cfg)
            merged_cfg.setdefault("api", cfg.get("api") or {})
            merged_cfg.setdefault("ws", cfg.get("ws") or {})
            try:
                account_listener = AccountListener(
                    config=merged_cfg,
                    state=state,
                    hedger=hedger,
                    telemetry=telemetry,
                )
                logging.getLogger("main").info("[main] AccountListener initialized")
            except Exception as exc:
                logging.getLogger("main").warning(
                    "[main] AccountListener init failed: %s", exc
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
    opt_cfg_ns = None
    if FundingOptimizer:
        opt_cfg_ns = _opt_cfg_from_dict(cfg)
        maker_updater = _MakerUpdater(maker, logging.getLogger("optimizer"))

        if getattr(opt_cfg_ns, "enabled", True) is False:
            logging.getLogger("optimizer").info("[optimizer] disabled via config")
            opt_cfg_ns = None

    if FundingOptimizer and opt_cfg_ns is not None:

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

    pnl_log_path = os.environ.get("PNL_LOG_PATH", "logs/pnl_stats.jsonl")
    last_pnl_written = {"maker_edge": 0.0, "taker_slippage": 0.0}

    async def periodic_core_metrics():
        while not stop_event.is_set():
            telemetry.set_gauge("uptime_seconds", max(0.0, time.time() - start_ts))
            if state and hasattr(state, "get_fee_stats"):
                try:
                    stats = state.get_fee_stats()
                    for key, value in stats.items():
                        telemetry.set_gauge(f"fees_{key}", float(value))
                except Exception as exc:
                    logging.getLogger("telemetry").debug("fee stats update failed: %s", exc)
            if state and hasattr(state, "get_pnl_stats"):
                try:
                    pnl_stats = state.get_pnl_stats()
                    for key, value in pnl_stats.items():
                        telemetry.set_gauge(f"pnl_{key}", float(value))
                    if any(
                        abs(pnl_stats.get(k, 0.0) - last_pnl_written.get(k, 0.0)) > 1e-9
                        for k in last_pnl_written
                    ):
                        try:
                            os.makedirs(os.path.dirname(pnl_log_path), exist_ok=True)
                            with open(pnl_log_path, "a", encoding="utf-8") as fh:
                                record = {
                                    "timestamp": time.time(),
                                    "maker_edge": float(pnl_stats.get("maker_edge", 0.0)),
                                    "taker_slippage": float(pnl_stats.get("taker_slippage", 0.0)),
                                }
                                fh.write(json.dumps(record) + "\n")
                            last_pnl_written.update(
                                {
                                    "maker_edge": pnl_stats.get("maker_edge", 0.0),
                                    "taker_slippage": pnl_stats.get("taker_slippage", 0.0),
                                }
                            )
                        except Exception as exc:
                            logging.getLogger("telemetry").debug("pnl persist failed: %s", exc)
                except Exception as exc:
                    logging.getLogger("telemetry").debug("pnl stats update failed: %s", exc)
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

    if chaos and chaos.enabled:
        # Start chaos injector background task
        tasks.append(asyncio.create_task(chaos.run(), name="chaos"))

    if replay_sim:
        # Replay mode: run simulator instead of listener
        async def run_replay():
            await replay_sim.run()
            stop_event.set()  # Stop when replay completes

        tasks.append(asyncio.create_task(run_replay(), name="replay"))
    elif listener:
        tasks.append(asyncio.create_task(run_component("listener", listener)))
    if optimizer:
        tasks.append(asyncio.create_task(run_component("optimizer", optimizer)))
    if selector:
        tasks.append(asyncio.create_task(run_component("selector", selector)))
    if maker:
        tasks.append(asyncio.create_task(run_component("maker", maker)))
    if hedger:
        tasks.append(asyncio.create_task(run_component("hedger", hedger)))
    if account_listener:
        tasks.append(
            asyncio.create_task(
                run_component("account_listener", account_listener)
            )
        )

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
        if shared_trading_client:
            try:
                await shared_trading_client.close()
            except Exception as exc:
                logging.getLogger("main").debug("[main] shared trading client close failed: %s", exc)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
