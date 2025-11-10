#!/usr/bin/env python3
"""
Apply a stored market profile to the active config.yaml.

Usage:
    python scripts/apply_profile.py --profile profiles/market_102.yaml \
        --config config.yaml
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def save_yaml(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)


def apply_profile(profile: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    maker_profile = profile.get("maker") or {}
    hedger_profile = profile.get("hedger") or {}
    guard_profile = profile.get("guard") or {}
    metadata = profile.get("metadata") or {}
    market = profile.get("market")

    maker_cfg = config.setdefault("maker", {})
    if market:
        maker_cfg["pair"] = market
    maker_cfg.update({k: v for k, v in maker_profile.items() if v is not None})
    if metadata.get("exchange_min_notional") is not None:
        maker_cfg["exchange_min_notional"] = metadata["exchange_min_notional"]

    hedger_cfg = config.setdefault("hedger", {})
    if market:
        hedger_cfg["market"] = market
    for key, value in hedger_profile.items():
        if value is not None:
            hedger_cfg[key] = value

    guard_cfg = config.setdefault("guard", {})
    for key, value in guard_profile.items():
        if value is not None:
            guard_cfg[key] = value

    return config


def write_metadata(meta: Dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"Stored instrument metadata at {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a market profile to config.yaml.")
    parser.add_argument("--profile", required=True, type=Path, help="Path to profile YAML.")
    parser.add_argument("--config", default=Path("config.yaml"), type=Path, help="Target config file.")
    parser.add_argument(
        "--metadata-out",
        type=Path,
        default=Path("data/instruments/last_profile.json"),
        help="Where to store associated metadata (default: %(default)s).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the diff without writing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    profile = load_yaml(args.profile)
    config = load_yaml(args.config)

    updated = apply_profile(profile, config)

    if args.dry_run:
        print("Dry run – not writing config. Resulting maker/hedger sections:")
        print(yaml.safe_dump({"maker": updated.get("maker"), "hedger": updated.get("hedger"), "guard": updated.get("guard")}, sort_keys=False))
    else:
        save_yaml(args.config, updated)
        print(f"Updated {args.config} with profile {args.profile}")

    metadata = profile.get("metadata") or {}
    if metadata:
        write_metadata(metadata, args.metadata_out)


if __name__ == "__main__":
    main()

