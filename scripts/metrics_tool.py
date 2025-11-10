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
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from metrics import MetricsCompositor, MetricsLedger  # noqa: E402


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

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

