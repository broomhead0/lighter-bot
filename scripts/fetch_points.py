#!/usr/bin/env python3
"""
Fetch the current Season 2 points snapshot for the configured Lighter account.

Usage:
  python scripts/fetch_points.py \
      --account 366110 \
      --base-url https://mainnet.zklighter.elliot.ai

Requires a bearer token (same as REST trade script). Provide via:
  export LIGHTER_API_BEARER="..."
or pass --token.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional

import requests


def fetch_points(base_url: str, account: int, token: str) -> Dict[str, Any]:
    candidates = [
        "/api/v1/referral/points",
        "/referral/points",
    ]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"account_index": account}
    for path in candidates:
        url = base_url.rstrip("/") + path
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
        except Exception:
            continue
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data
    raise SystemExit(
        "Unable to fetch points from Lighter API. Tried: {}".format(
            ", ".join(candidates)
        )
    )


def summarise(points: Dict[str, Any], account: int) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "account_index": account,
        "user_total_points": points.get("user_total_points"),
        "user_last_week_points": points.get("user_last_week_points"),
        "user_total_referral_reward_points": points.get(
            "user_total_referral_reward_points"
        ),
        "user_last_week_referral_reward_points": points.get(
            "user_last_week_referral_reward_points"
        ),
        "reward_point_multiplier": points.get("reward_point_multiplier"),
    }
    referrals = points.get("referrals")
    if isinstance(referrals, list):
        summary["referral_count"] = len(referrals)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Lighter points snapshot.")
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--account",
        type=int,
        required=True,
        help="Account index to query (e.g. 366110)",
    )
    parser.add_argument(
        "--token",
        help="Bearer token (falls back to LIGHTER_API_BEARER env var)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of summary.",
    )
    args = parser.parse_args()

    token = args.token or os.getenv("LIGHTER_API_BEARER")
    if not token:
        raise SystemExit("Set LIGHTER_API_BEARER or pass --token.")

    data = fetch_points(args.base_url, args.account, token)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        summary = summarise(data, args.account)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

