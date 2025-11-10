#!/usr/bin/env python3
"""Fetch and print telemetry metrics from the running bot service.

Usage examples:

    python scripts/dump_metrics.py
    python scripts/dump_metrics.py --filter portfolio_
    python scripts/dump_metrics.py --names portfolio_total_quote portfolio_fees_paid

Designed to run locally *or* inside the Railway container via:

    railway ssh --service lighter-bot -- python scripts/dump_metrics.py --filter portfolio_
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def fetch_metrics(host: str, port: int, timeout: float) -> str:
    url = f"http://{host}:{port}/metrics"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        payload = resp.read()
    return payload.decode("utf-8", errors="replace")


def filter_metrics(content: str, names: list[str], filters: list[str]) -> list[str]:
    lines: list[str] = []
    for line in content.splitlines():
        if not line or line.startswith("#"):
            continue
        metric_name = line.split()[0]
        if names:
            if metric_name in names:
                lines.append(line)
            continue
        if filters:
            if any(token in line for token in filters):
                lines.append(line)
            continue
        lines.append(line)
    return lines


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump telemetry metrics from the bot.")
    parser.add_argument("--host", default="127.0.0.1", help="Telemetry host (default: %(default)s)")
    parser.add_argument("--port", default=9100, type=int, help="Telemetry port (default: %(default)s)")
    parser.add_argument(
        "--timeout", default=5.0, type=float, help="HTTP timeout in seconds (default: %(default)s)"
    )
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help="Substring filter applied to metric lines (can be repeated)",
    )
    parser.add_argument(
        "--names",
        nargs="*",
        default=[],
        help="Exact metric names to include (overrides --filter when provided)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        content = fetch_metrics(args.host, args.port, args.timeout)
    except urllib.error.URLError as exc:
        print(f"error: failed to fetch metrics from {args.host}:{args.port} ({exc})", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive catch
        print(f"error: unexpected failure fetching metrics: {exc}", file=sys.stderr)
        return 1

    selected = filter_metrics(content, args.names, args.filter)
    if not selected:
        print("# no metrics matched the provided filters", file=sys.stderr)
        return 3

    print("\n".join(selected))
    return 0


if __name__ == "__main__":
    sys.exit(main())

