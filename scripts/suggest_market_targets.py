#!/usr/bin/env python3
"""
Suggest Lighter markets that are likely point-boost candidates.

Heuristic:
  - Prefers lower-liquidity markets (lower 24h volume / open interest).
  - Gives extra weight to newly listed contracts (if listing timestamp present).
  - Outputs a ranked table or JSON so we can steer the maker engine.

Usage:
    python scripts/suggest_market_targets.py \
        --base-url https://mainnet.zklighter.elliot.ai \
        --top 5
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

import requests


def _pick(entry: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for key in keys:
        if key in entry and entry[key] not in (None, "", "null"):
            return entry[key]
    return None


def fetch_markets(base_url: str) -> List[Dict[str, Any]]:
    candidates = [
        "/api/v1/public/markets",
        "/api/v1/markets",
        "/markets",
    ]
    for path in candidates:
        url = base_url.rstrip("/") + path
        try:
            resp = requests.get(url, timeout=15)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        data = resp.json()
        if isinstance(data, dict):
            if "markets" in data and isinstance(data["markets"], list):
                return data["markets"]
        elif isinstance(data, list):
            return data
    raise SystemExit(
        "Unable to fetch market stats from Lighter API. "
        "Tried endpoints: {}".format(", ".join(candidates))
    )


def to_decimal(value: Any) -> Optional[Decimal]:
    if value in (None, "", "null"):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def normalise(values: List[Decimal]) -> List[float]:
    if not values:
        return []
    nums = [float(v) for v in values]
    low, high = min(nums), max(nums)
    if math.isclose(low, high):
        return [0.5 for _ in nums]
    return [(x - low) / (high - low) for x in nums]


def compute_scores(markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = dt.datetime.utcnow()
    parsed: List[Dict[str, Any]] = []
    for entry in markets:
        symbol = _pick(entry, ("symbol", "market", "name", "instrument"))
        if not symbol:
            continue
        vol = to_decimal(
            _pick(
                entry,
                (
                    "volume_24h",
                    "volume_usd_24h",
                    "volume_quote_24h",
                    "recent_volume",
                    "usd_volume",
                ),
            )
        )
        oi = to_decimal(
            _pick(entry, ("open_interest", "open_interest_usd", "oi_usd", "total_oi"))
        )
        listing_ts = _pick(
            entry,
            (
                "listing_timestamp",
                "listed_at",
                "created_at",
                "launch_timestamp",
            ),
        )
        if listing_ts is not None:
            try:
                if isinstance(listing_ts, (int, float)):
                    # assume seconds; if ms adjust later
                    ts = float(listing_ts)
                    if ts > 10_000_000_000:  # ms
                        ts /= 1000.0
                    listing_dt = dt.datetime.utcfromtimestamp(ts)
                else:
                    listing_dt = dt.datetime.fromisoformat(str(listing_ts))
            except Exception:
                listing_dt = None
        else:
            listing_dt = None
        parsed.append(
            {
                "symbol": str(symbol),
                "volume": vol or Decimal("0"),
                "open_interest": oi or Decimal("0"),
                "listing_dt": listing_dt,
                "raw": entry,
            }
        )

    volumes = [p["volume"] for p in parsed]
    ois = [p["open_interest"] for p in parsed]
    vol_norm = normalise(volumes)
    oi_norm = normalise(ois)

    for idx, market in enumerate(parsed):
        vol_factor = vol_norm[idx] if idx < len(vol_norm) else 0.5
        oi_factor = oi_norm[idx] if idx < len(oi_norm) else 0.5
        # Lower volume/open interest should rank higher -> invert.
        low_liq_score = (1 - vol_factor) * 0.6 + (1 - oi_factor) * 0.3
        age_score = 0.1
        if market["listing_dt"]:
            age_hours = (now - market["listing_dt"]).total_seconds() / 3600.0
            if age_hours <= 0:
                age_score = 0.3
            else:
                age_score = max(0.0, min(0.3, 30.0 / max(age_hours, 1.0) * 0.3))
        score = low_liq_score + age_score
        market["score"] = score
        market["volume_usd"] = float(market["volume"])
        market["open_interest_usd"] = float(market["open_interest"])
        market["listing_age_hours"] = (
            (now - market["listing_dt"]).total_seconds() / 3600.0
            if market["listing_dt"]
            else None
        )

    parsed.sort(key=lambda x: x["score"], reverse=True)
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Suggest Lighter markets likely to receive point boosts."
    )
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="How many markets to show (default: %(default)s)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of a table.",
    )
    args = parser.parse_args()

    markets = fetch_markets(args.base_url)
    ranked = compute_scores(markets)
    top_markets = ranked[: args.top]

    if args.json:
        print(json.dumps(top_markets, indent=2, default=str))
        return

    print(f"Top {len(top_markets)} candidate markets (likely boosts):")
    print(
        f"{'Rank':>4}  {'Market':<12} {'Score':>6}  {'Vol(24h)':>12}  {'OpenInt':>12}  {'Age(h)':>8}"
    )
    for idx, market in enumerate(top_markets, start=1):
        vol = market["volume_usd"]
        oi = market["open_interest_usd"]
        age = market["listing_age_hours"]
        age_display = f"{age:6.1f}" if age is not None else "  N/A "
        print(
            f"{idx:>4}  {market['symbol']:<12} {market['score']:6.3f}  "
            f"{vol:12.2f}  {oi:12.2f}  {age_display}"
        )

    print("\nScores favour newly listed, lower-liquidity markets.")
    print("Cross-check with Friday points announcement before committing capital.")


if __name__ == "__main__":
    main()

