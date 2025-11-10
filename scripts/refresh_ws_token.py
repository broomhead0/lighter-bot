#!/usr/bin/env python3
"""
Generate a fresh WS auth token and update Railway + local .env snapshot.

Requires `lighter-python` and the Railway CLI to be installed. Credentials are
read from environment variables so secrets never touch the repo:

    API_KEY_PRIVATE_KEY   (hex string, 0x-prefixed)
    ACCOUNT_INDEX         (int)
    API_KEY_INDEX         (int)
    API_BASE_URL          (default: https://mainnet.zklighter.elliot.ai)

On success we:
  - Print the new token (so callers can capture it in CI logs with redaction).
  - Write/overwrite `.env.ws_token` locally for quick sourcing.
  - Update Railway variables `WS_AUTH_TOKEN` and `LIGHTER_API_BEARER`.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    from lighter import SignerClient
except ImportError as exc:  # pragma: no cover
    print(
        "Error: lighter-python package not installed. "
        "Install with `pip install \"git+https://github.com/elliottech/lighter-python.git\"`.",
        file=sys.stderr,
    )
    raise


def env_or_exit(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise SystemExit(f"Environment variable {key} is required.")
    return value


def update_local_env(token: str, path: Path) -> None:
    path.write_text(f"WS_AUTH_TOKEN={token}\nLIGHTER_API_BEARER={token}\n")
    print(f"Wrote local token snapshot to {path}")


def update_config_yaml(token: str, config_path: Path) -> None:
    import yaml  # type: ignore
    if not config_path.exists():
        return
    with config_path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    api_cfg = cfg.setdefault("api", {})
    api_cfg["base_url"] = api_cfg.get("base_url") or os.environ.get("API_BASE_URL")
    cfg.setdefault("ws", {})["auth_token"] = token
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)
    print(f"Updated {config_path} with latest auth token.")


def update_railway(token: str, dry_run: bool) -> None:
    if dry_run:
        print("[dry-run] Skipping Railway variable updates.")
        return
    for var in ("WS_AUTH_TOKEN", "LIGHTER_API_BEARER"):
        cmd = [
            "railway",
            "variables",
            "--set",
            f"{var}={token}",
        ]
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)


async def generate_token(
    base_url: str,
    private_key: str,
    account_index: int,
    api_key_index: int,
    expiry_seconds: int,
) -> str:
    signer = SignerClient(
        url=base_url,
        private_key=private_key,
        account_index=account_index,
        api_key_index=api_key_index,
    )
    try:
        token, err = signer.create_auth_token_with_expiry(deadline=expiry_seconds)
        if err:
            raise RuntimeError(err)
        return token
    finally:
        await signer.close()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh WS auth token")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("API_BASE_URL", "https://mainnet.zklighter.elliot.ai"),
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--expiry-seconds",
        type=int,
        default=3600,
        help="Token lifetime (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default=".env.ws_token",
        help="Local file to write token snapshot (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Railway variable updates; just print and write local file.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)

    private_key = env_or_exit("API_KEY_PRIVATE_KEY")
    account_index = int(env_or_exit("ACCOUNT_INDEX"))
    api_key_index = int(env_or_exit("API_KEY_INDEX"))

    token = asyncio.run(
        generate_token(
            base_url=args.base_url,
            private_key=private_key,
            account_index=account_index,
            api_key_index=api_key_index,
            expiry_seconds=args.expiry_seconds,
        )
    )

    print(f"WS token: {token}")
    update_local_env(token, Path(args.output))
    update_railway(token, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

