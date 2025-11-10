#!/usr/bin/env python3
"""
Metrics toolbox for the Lighter bot.

Examples:

    python scripts/metrics_tool.py dump
    python scripts/metrics_tool.py window --hours 6
    python scripts/metrics_tool.py reset --confirm
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from metrics import FillEvent, MetricsCompositor, MetricsLedger  # noqa: E402


DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _ledger_from_config(cfg: dict) -> MetricsLedger:
    metrics_cfg = cfg.get("metrics") or {}
    path = Path(metrics_cfg.get("ledger_path", "data/metrics/fills.jsonl"))
    archive = metrics_cfg.get("archive_dir")
    archive_path = Path(archive) if archive else path.parent / "archive"
    max_bytes = metrics_cfg.get("max_bytes")
    return MetricsLedger(path, archive_dir=archive_path, max_bytes=max_bytes)


def _compositor_from_config(cfg: dict) -> MetricsCompositor:
    ledger = _ledger_from_config(cfg)
    return MetricsCompositor(ledger)


def cmd_dump(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    compositor = _compositor_from_config(cfg)
    total = compositor.snapshot()
    window_seconds = cfg.get("metrics", {}).get("rolling_window_seconds", 6 * 3600)
    rolling = compositor.snapshot(window_seconds=window_seconds)

    payload = {
        "total": total.as_dict(),
        f"last_{int(window_seconds // 3600)}h": rolling.as_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_window(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    compositor = _compositor_from_config(cfg)
    window_seconds = args.hours * 3600 if args.hours else args.seconds
    snapshot = compositor.snapshot(window_seconds=window_seconds)
    print(json.dumps(snapshot.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("error: pass --confirm to archive/reset the ledger", file=sys.stderr)
        return 2
    cfg = load_config(Path(args.config))
    ledger = _ledger_from_config(cfg)
    archive = ledger.reset()
    if archive:
        print(f"ledger archived to {archive}")
    else:
        print("ledger reset (no archive path configured)")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    ledger = _ledger_from_config(cfg)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    since_ts: Optional[float] = None
    if args.hours:
        since_ts = time.time() - args.hours * 3600
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write("timestamp,market,role,side,size,price,notional,base_delta,quote_delta,fee_paid,mid_price,trade_id,source\n")
        for event in ledger.iter_events(since_ts=since_ts):
            row = [
                f"{event.timestamp:.3f}",
                event.market,
                event.role,
                event.side,
                event.size,
                event.price,
                event.notional,
                event.base_delta,
                event.quote_delta,
                event.fee_paid,
                event.mid_price or "",
                str(event.trade_id or ""),
                event.source,
            ]
            fh.write(",".join(row) + "\n")
    print(f"exported fills to {out_path}")
    return 0


def _load_trades_from_file(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "trades" in data:
        trades = data["trades"]
    elif isinstance(data, list):
        trades = data
    else:
        raise ValueError("unsupported JSON structure; expected list or {\"trades\": [...]}")
    if not isinstance(trades, list):
        raise ValueError("trades must be a list")
    return trades


def _derive_role(trade: dict, account_index: int) -> tuple[str, str]:
    ask_account = trade.get("ask_account_id") or trade.get("ask_account")
    bid_account = trade.get("bid_account_id") or trade.get("bid_account")
    maker_is_ask = bool(trade.get("is_maker_ask"))
    side = "ask"
    role = "taker"
    if ask_account is not None and int(ask_account) == account_index:
        side = "ask"
        role = "maker" if maker_is_ask else "taker"
    elif bid_account is not None and int(bid_account) == account_index:
        side = "bid"
        role = "maker" if not maker_is_ask else "taker"
    return role, side


def _normalise_timestamp(ts: float) -> float:
    if ts > 1e12:  # milliseconds
        return ts / 1000.0
    return ts


def cmd_import_json(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    account_index = args.account_index or (cfg.get("api") or {}).get("account_index")
    if account_index is None:
        print("error: account index missing (pass --account-index or set api.account_index)", file=sys.stderr)
        return 2
    trades = _load_trades_from_file(Path(args.input))
    ledger = _ledger_from_config(cfg)
    existing_ids = {
        event.trade_id
        for event in ledger.iter_events()
        if event.trade_id is not None
    }
    fees_cfg = cfg.get("fees") or {}
    maker_rate = Decimal(str(fees_cfg.get("maker_actual_rate", 0)))
    taker_rate = Decimal(str(fees_cfg.get("taker_actual_rate", 0)))
    appended = 0

    for trade in sorted(trades, key=lambda x: x.get("timestamp", 0)):
        trade_id = trade.get("trade_id")
        if trade_id is not None and trade_id in existing_ids:
            continue
        role, side = _derive_role(trade, int(account_index))
        size = Decimal(str(trade.get("size") or trade.get("base_amount") or trade.get("quantity") or "0"))
        price = Decimal(str(trade.get("price") or trade.get("mark_price") or "0"))
        notional = Decimal(str(trade.get("usd_amount") or trade.get("notional") or trade.get("trade_value") or size * price))

        base_delta = size if side == "bid" else -size
        quote_delta = -base_delta * price
        fee_rate = maker_rate if role == "maker" else taker_rate
        fee = abs(notional) * fee_rate
        fee_currency = "quote" if fee != 0 else None
        mid = trade.get("mid_price")

        event = FillEvent(
            timestamp=_normalise_timestamp(float(trade.get("timestamp", time.time()))),
            market=f"market:{trade.get('market_id') or trade.get('market')}",
            role=role,
            side=side,
            size=str(size),
            price=str(price),
            notional=str(notional),
            base_delta=str(base_delta),
            quote_delta=str(quote_delta),
            fee_paid=str(fee),
            mid_price=str(mid) if mid is not None else None,
            trade_id=int(trade_id) if trade_id is not None else None,
            source="backfill",
            fee_currency=fee_currency,
        )
        ledger.append(event)
        appended += 1

    print(f"imported {appended} trades into ledger")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Metrics CLI for Lighter bot")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.yaml")

    sub = parser.add_subparsers(dest="cmd", required=True)

    dump_p = sub.add_parser("dump", help="Show total metrics and default rolling window")
    dump_p.set_defaults(func=cmd_dump)

    window_p = sub.add_parser("window", help="Show metrics for a specific window")
    window_p.add_argument("--hours", type=float, help="Hours to look back")
    window_p.add_argument("--seconds", type=float, help="Seconds to look back (overrides --hours)")
    window_p.set_defaults(func=cmd_window)

    reset_p = sub.add_parser("reset", help="Archive/reset the ledger")
    reset_p.add_argument("--confirm", action="store_true", help="Confirm the destructive action")
    reset_p.set_defaults(func=cmd_reset)

    export_p = sub.add_parser("export", help="Export ledger fills to CSV")
    export_p.add_argument("--output", required=True, help="Destination CSV file")
    export_p.add_argument("--hours", type=float, help="Optional hours window to limit export")
    export_p.set_defaults(func=cmd_export)

    import_p = sub.add_parser("import-json", help="Import trades from JSON into ledger")
    import_p.add_argument("--input", required=True, help="Path to trades JSON file (list or {\"trades\": [...]})")
    import_p.add_argument(
        "--account-index",
        type=int,
        help="Override account index (defaults to api.account_index from config)",
    )
    import_p.set_defaults(func=cmd_import_json)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

