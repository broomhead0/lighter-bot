#!/usr/bin/env python3
"""
Convenience utility to retarget the bot to a new Lighter market.

Usage examples:

    python scripts/set_market.py --symbol ICP --balance-usd 30
    python scripts/set_market.py --market-id 102 --dry-run

The script fetches order book metadata via the lighter-python SDK so we stay in
sync with exchange precision, minimum order sizes, and fee params. It then
updates the key knobs inside config.yaml (maker + hedger blocks) so we do not
fat-finger scale factors when rotating markets.
"""
from __future__ import annotations

import argparse
import asyncio
import math
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

try:
    from lighter.configuration import Configuration
    from lighter.api_client import ApiClient
    from lighter.api.order_api import OrderApi
except ImportError as exc:  # pragma: no cover - requires lighter-python at runtime
    print(
        "Error: lighter-python package not found. Install with "
        "`pip install \"git+https://github.com/elliottech/lighter-python.git\"`.",
        file=sys.stderr,
    )
    raise


@dataclass
class MarketMetadata:
    market_id: int
    symbol: str
    min_base_amount: Decimal
    min_quote_amount: Decimal
    price_decimals: int
    size_decimals: int
    quote_multiplier: int
    last_trade_price: Decimal
    initial_margin_bps: int
    maintenance_margin_bps: int


def _round(value: Decimal, decimals: int) -> float:
    quant = Decimal("1").scaleb(-decimals)
    return float(value.quantize(quant, rounding=ROUND_HALF_UP))


async def fetch_market_metadata(
    base_url: str,
    market_id: Optional[int],
    symbol: Optional[str],
) -> MarketMetadata:
    cfg = Configuration(host=base_url)
    client = ApiClient(configuration=cfg)
    api = OrderApi(api_client=client)
    try:
        resp = await api.order_book_details()
    finally:
        await client.close()

    match = None
    wanted_symbol = symbol.upper() if symbol else None
    for entry in resp.order_book_details:
        if market_id is not None and entry.market_id != market_id:
            continue
        if wanted_symbol and entry.symbol.upper() != wanted_symbol:
            continue
        match = entry
        break

    if match is None:
        raise SystemExit(
            f"No market metadata found for "
            f"{'market_id='+str(market_id) if market_id is not None else ''}"
            f"{' symbol='+symbol if symbol else ''}."
        )

    return MarketMetadata(
        market_id=match.market_id,
        symbol=match.symbol,
        min_base_amount=Decimal(str(match.min_base_amount)),
        min_quote_amount=Decimal(str(match.min_quote_amount)),
        price_decimals=int(match.supported_price_decimals),
        size_decimals=int(match.supported_size_decimals),
        quote_multiplier=int(match.quote_multiplier),
        last_trade_price=Decimal(str(match.last_trade_price)),
        initial_margin_bps=int(match.default_initial_margin_fraction),
        maintenance_margin_bps=int(match.maintenance_margin_fraction),
    )


def compute_sizing(
    meta: MarketMetadata,
    balance_usd: Optional[Decimal],
    sizing_multiplier: float,
    baseline_margin_bps: int,
    spread_bps: float,
) -> Dict[str, float]:
    min_clip = meta.min_base_amount
    cushion = Decimal("0.98")
    min_quote_units = (
        meta.min_quote_amount / (meta.last_trade_price * cushion)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if min_quote_units > min_clip:
        min_clip = min_quote_units
    # size_max caps at 2x min or balance-based constraint
    size_max = min_clip * Decimal(str(sizing_multiplier))
    if balance_usd:
        max_units_from_balance = (balance_usd / meta.last_trade_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        # keep half of balance available for hedges -> divide by 2
        max_units_from_balance = max_units_from_balance / 2
        if max_units_from_balance < min_clip:
            raise SystemExit(
                f"Balance ${balance_usd} is below the exchange minimum for {meta.symbol} "
                f"(min clip {min_clip} units ≈ ${min_clip * meta.last_trade_price:.2f})."
            )
        size_max = min(size_max, max_units_from_balance)
    size_max = size_max.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    size_min = min_clip
    size = (size_min + size_max) / 2
    inventory_cap = (size_max * Decimal("2")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    trigger_units = (size_max * Decimal("1.5")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    target_units = (size_min * Decimal("0.5")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    max_clip = size_min
    # Adjust sizing for markets with lower leverage (higher margin fraction).
    if meta.initial_margin_bps > 0 and baseline_margin_bps > 0:
        margin_scale = min(1.0, baseline_margin_bps / float(meta.initial_margin_bps))
        if margin_scale < 1.0:
            scale_decimal = Decimal(str(margin_scale))
            size = max(min_clip, (Decimal(str(size)) * scale_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            size_min = max(min_clip, (Decimal(str(size_min)) * scale_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            size_max = max(min_clip, (Decimal(str(size_max)) * scale_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            inventory_cap = max(min_clip, (Decimal(str(inventory_cap)) * scale_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            trigger_units = max(min_clip, (Decimal(str(trigger_units)) * scale_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            target_units = max(min_clip * Decimal("0.1"), (Decimal(str(target_units)) * scale_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            max_clip = max(min_clip, (Decimal(str(max_clip)) * scale_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    if size_max <= size_min:
        size_max = (Decimal(str(size_min)) * Decimal("1.20")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    if size <= size_min:
        size = (Decimal(str(size_min)) * Decimal("1.10")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


    trigger_notional = float(
        max(
            meta.min_quote_amount,
            (trigger_units * meta.last_trade_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
        )
    )

    return {
        "size": _round(size, meta.size_decimals),
        "size_min": _round(size_min, meta.size_decimals),
        "size_max": _round(size_max, meta.size_decimals),
        "inventory_soft_cap": _round(inventory_cap, meta.size_decimals),
        "trigger_units": _round(trigger_units, meta.size_decimals),
        "target_units": _round(target_units, meta.size_decimals),
        "max_clip_units": _round(max_clip, meta.size_decimals),
        "trigger_notional": trigger_notional,
        "exchange_min_notional": float(meta.min_quote_amount),
        "spread_bps": spread_bps,
        "initial_margin_bps": meta.initial_margin_bps,
        "maintenance_margin_bps": meta.maintenance_margin_bps,
    }


def update_config(
    cfg: Dict[str, Any],
    meta: MarketMetadata,
    sizing: Dict[str, float],
) -> Dict[str, Any]:
    maker = cfg.setdefault("maker", {})
    maker["pair"] = f"market:{meta.market_id}"
    maker["size"] = sizing["size"]
    maker["size_min"] = sizing["size_min"]
    maker["size_max"] = sizing["size_max"]
    maker["exchange_min_size"] = sizing["size_min"]
    maker["inventory_soft_cap"] = sizing["inventory_soft_cap"]
    maker["price_scale"] = 10 ** meta.price_decimals
    maker["size_scale"] = 10 ** meta.size_decimals
    maker["exchange_min_notional"] = sizing["exchange_min_notional"]

    hedger = cfg.setdefault("hedger", {})
    hedger["market"] = f"market:{meta.market_id}"
    hedger["trigger_units"] = sizing["trigger_units"]
    hedger["target_units"] = sizing["target_units"]
    hedger["max_clip_units"] = sizing["max_clip_units"]
    hedger["trigger_notional"] = sizing["trigger_notional"]

    guard_cfg = cfg.setdefault("guard", {})
    guard_units = sizing["inventory_soft_cap"] * 2.0
    new_max_units = round(guard_units, meta.size_decimals)
    new_max_notional = round(guard_units * float(meta.last_trade_price), 2)
    guard_cfg["max_position_units"] = max(
        float(guard_cfg.get("max_position_units", 0.0)), new_max_units
    )
    guard_cfg["max_inventory_notional"] = max(
        float(guard_cfg.get("max_inventory_notional", 0.0)), new_max_notional
    )

    return cfg


def render_profile(meta: MarketMetadata, sizing: Dict[str, float]) -> Dict[str, Any]:
    return {
        "market": f"market:{meta.market_id}",
        "symbol": meta.symbol,
        "maker": {
            "size": sizing["size"],
            "size_min": sizing["size_min"],
            "size_max": sizing["size_max"],
            "exchange_min_size": sizing["size_min"],
            "inventory_soft_cap": sizing["inventory_soft_cap"],
            "spread_bps": sizing.get("spread_bps", None),
            "price_scale": 10 ** meta.price_decimals,
            "size_scale": 10 ** meta.size_decimals,
            "volatility": None,  # filled by user
        },
        "hedger": {
            "trigger_units": sizing["trigger_units"],
            "target_units": sizing["target_units"],
            "max_clip_units": sizing["max_clip_units"],
            "trigger_notional": sizing["trigger_notional"],
            "price_offset_bps": None,
            "max_slippage_bps": None,
        },
        "guard": {
            "max_position_units": sizing["inventory_soft_cap"] * 2.0,
            "max_inventory_notional": sizing["inventory_soft_cap"] * 2.0 * float(meta.last_trade_price),
            "price_band_bps": None,
        },
        "metadata": {
            "initial_margin_bps": meta.initial_margin_bps,
            "maintenance_margin_bps": meta.maintenance_margin_bps,
            "exchange_min_notional": sizing["exchange_min_notional"],
            "min_quote_amount": float(meta.min_quote_amount),
            "min_base_amount": float(meta.min_base_amount),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retarget config.yaml to another market.")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml (default: %(default)s)",
    )
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--market-id",
        type=int,
        help="Numeric market id (e.g. 102 for ICP).",
    )
    parser.add_argument(
        "--symbol",
        help="Market symbol (e.g. ICP). Case insensitive.",
    )
    parser.add_argument(
        "--balance-usd",
        type=float,
        help="Approximate capital available so sizing stays within budget.",
    )
    parser.add_argument(
        "--sizing-multiplier",
        type=float,
        default=1.5,
        help="Multiplier applied to the exchange minimum to set maker.size_max "
        "(default: %(default)s).",
    )
    parser.add_argument(
        "--baseline-margin-bps",
        type=int,
        default=666,
        help="Reference initial margin (in bps) used for scaling clip sizes when leverage is lower. "
        "(default: %(default)s, roughly SOL perps).",
    )
    parser.add_argument(
        "--spread-bps",
        type=float,
        default=7.0,
        help="Default maker spread to store in the profile (default: %(default)s).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned changes without writing config.yaml.",
    )
    parser.add_argument(
        "--profile-out",
        type=Path,
        help="If provided, write the computed profile to this path instead of updating config.yaml.",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Apply the computed profile to config.yaml immediately.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.market_id and not args.symbol:
        raise SystemExit("Provide either --market-id or --symbol.")

    balance = Decimal(str(args.balance_usd)) if args.balance_usd else None

    meta = asyncio.run(
        fetch_market_metadata(
            base_url=args.base_url,
            market_id=args.market_id,
            symbol=args.symbol,
        )
    )

    sizing = compute_sizing(
        meta,
        balance,
        args.sizing_multiplier,
        args.baseline_margin_bps,
        args.spread_bps,
    )

    if args.profile_out:
        profile = render_profile(meta, sizing)
        args.profile_out.parent.mkdir(parents=True, exist_ok=True)
        with args.profile_out.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(profile, fh, sort_keys=False)
        print(f"Wrote profile for {meta.symbol} to {args.profile_out}")
        if not args.activate:
            return

    with open(args.config, "r") as fh:
        cfg = yaml.safe_load(fh)

    updated = update_config(cfg, meta, sizing)

    if args.dry_run and not args.activate:
        print(
            "Dry run – planned updates:\n"
            f"  maker.pair -> market:{meta.market_id} ({meta.symbol})\n"
            f"  maker.size -> {sizing['size']}\n"
            f"  maker.size_min -> {sizing['size_min']}\n"
            f"  maker.size_max -> {sizing['size_max']}\n"
            f"  maker.exchange_min_size -> {sizing['size_min']}\n"
            f"  maker.inventory_soft_cap -> {sizing['inventory_soft_cap']}\n"
            f"  maker.price_scale -> {10 ** meta.price_decimals}\n"
            f"  maker.size_scale -> {10 ** meta.size_decimals}\n"
            f"  hedger.market -> market:{meta.market_id}\n"
            f"  hedger.trigger_units -> {sizing['trigger_units']}\n"
            f"  hedger.target_units -> {sizing['target_units']}\n"
            f"  hedger.max_clip_units -> {sizing['max_clip_units']}\n"
            f"  hedger.trigger_notional -> {sizing['trigger_notional']:.2f}"
        )
        return

    with open(args.config, "w") as fh:
        yaml.safe_dump(updated, fh, sort_keys=False, allow_unicode=False)

    print(
        f"Updated {args.config} for {meta.symbol} (market:{meta.market_id}). "
        f"maker.size={sizing['size']} size_min={sizing['size_min']} "
        f"size_max={sizing['size_max']} inventory_cap={sizing['inventory_soft_cap']} "
        f"hedger trigger_units={sizing['trigger_units']}."
    )


if __name__ == "__main__":
    main()

