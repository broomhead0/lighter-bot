#!/usr/bin/env python3
"""
Fetch recent trades for the configured Lighter account via the REST API.

Usage:
    python scripts/fetch_trades.py --limit 200 --output logs/trades/latest.json

Requirements:
    - Environment variable `LIGHTER_API_BEARER` (or pass `--token`) containing
      a valid bearer token for the Lighter REST API.
    - `config.yaml` should contain the API base URL and account identifiers,
      or pass overrides via CLI flags.
"""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping, Optional

import requests
import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


def load_config(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def pick_first(entry: Mapping[str, object], keys: Iterable[str]) -> Optional[object]:
    for key in keys:
        value = entry.get(key)
        if value not in (None, "", "null"):
            return value
    return None


def to_decimal(value: object) -> Optional[Decimal]:
    if value in (None, "", "null"):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def summarise_trades(trades: Iterable[Mapping[str, object]], account_index: int) -> Mapping[str, object]:
    maker_pnl = Decimal("0")
    taker_pnl = Decimal("0")
    maker_notional = Decimal("0")
    taker_notional = Decimal("0")
    maker_count = 0
    taker_count = 0

    for trade in trades:
        # Determine our role based on account participation fields.
        ask_account = pick_first(trade, ("ask_account_id", "ask_account"))
        bid_account = pick_first(trade, ("bid_account_id", "bid_account"))
        is_maker_ask = trade.get("is_maker_ask")

        role = ""
        try:
            ask_account = int(ask_account) if ask_account is not None else None
        except Exception:
            ask_account = None
        try:
            bid_account = int(bid_account) if bid_account is not None else None
        except Exception:
            bid_account = None

        if ask_account == account_index and is_maker_ask is True:
            role = "maker"
        elif bid_account == account_index and is_maker_ask is False:
            role = "maker"
        elif ask_account == account_index or bid_account == account_index:
            role = "taker"

        size = to_decimal(pick_first(trade, ("size", "quantity", "base_amount", "base_size")))
        price = to_decimal(pick_first(trade, ("price", "mark_price")))
        trade_value = to_decimal(pick_first(trade, ("usd_amount", "trade_value", "notional", "value")))
        pnl = to_decimal(
            pick_first(trade, ("closed_pnl", "pnl", "realized_pnl", "realised_pnl"))
        )

        if trade_value is None and size is not None and price is not None:
            trade_value = size * price

        if role == "maker":
            maker_count += 1
            if trade_value is not None:
                maker_notional += trade_value
            if pnl is not None:
                maker_pnl += pnl
        elif role == "taker":
            taker_count += 1
            if trade_value is not None:
                taker_notional += trade_value
            if pnl is not None:
                taker_pnl += pnl

    summary = {
        "maker_count": maker_count,
        "taker_count": taker_count,
        "maker_notional": float(maker_notional),
        "taker_notional": float(taker_notional),
        "maker_pnl": float(maker_pnl),
        "taker_pnl": float(taker_pnl),
        "net_pnl": float(maker_pnl + taker_pnl),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch trade history from Lighter REST API.")
    parser.add_argument("--limit", type=int, default=200, help="Number of trades to fetch (default: 200)")
    parser.add_argument("--output", type=Path, help="Optional path to write JSON output")
    parser.add_argument("--account", type=str, help="Override account identifier/index")
    parser.add_argument("--base-url", type=str, help="Override API base URL")
    parser.add_argument(
        "--token",
        type=str,
        help="Bearer token for REST API (falls back to LIGHTER_API_BEARER env var)",
    )
    args = parser.parse_args()

    cfg = load_config(CONFIG_PATH)
    api_cfg = cfg.get("api") or {}

    base_url = args.base_url or api_cfg.get("base_url") or "https://mainnet.zklighter.elliot.ai"
    account = args.account or api_cfg.get("account_index")
    if account is None:
        raise SystemExit("Account identifier missing. Set api.account_index in config.yaml or pass --account.")

    token = args.token or os.getenv("LIGHTER_API_BEARER")
    if not token:
        raise SystemExit("Missing auth token. Set LIGHTER_API_BEARER or pass --token.")

    url = f"{base_url.rstrip('/')}/api/v1/trades"
    params = {
        "account_index": account,
        "limit": args.limit,
        "sort_by": "timestamp",
        "sort_dir": "desc",
        "auth": token,
    }

    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        raise SystemExit(f"Request failed ({response.status_code}): {response.text}")

    data = response.json()
    # Some endpoints wrap the payload.
    trades = data.get("trades") if isinstance(data, dict) else data
    if trades is None:
        raise SystemExit("Unexpected response structure: no trades found.")

    summary = summarise_trades(trades, int(account))

    print(json.dumps(summary, indent=2))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as fh:
            json.dump(trades, fh, indent=2)
        print(f"Wrote {len(trades)} trades to {args.output}")


if __name__ == "__main__":
    main()

