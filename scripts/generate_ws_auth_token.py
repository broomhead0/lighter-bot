#!/usr/bin/env python3
"""Generate a Lighter WebSocket auth token.

Requires the `lighter-python` package from https://github.com/elliottech/lighter-python.

Example:

    pip install lighter-python
    python scripts/generate_ws_auth_token.py \
        --base-url https://mainnet.zklighter.elliot.ai \
        --account-index 12345 \
        --api-key-index 2 \
        --api-key-private-key 0xYOUR_PRIVATE_KEY

You can optionally pass --expiry-seconds (defaults to 3600).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional

try:
    from lighter import SignerClient
except ImportError as exc:  # pragma: no cover - only hit when deps missing
    print(
        "Error: lighter-python package not found. Install with `pip install lighter-python`.",
        file=sys.stderr,
    )
    raise


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Lighter WS auth token")
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key-private-key",
        required=True,
        help="Hex-encoded API key private key",
    )
    parser.add_argument(
        "--account-index",
        type=int,
        required=True,
        help="Your Lighter account index",
    )
    parser.add_argument(
        "--api-key-index",
        type=int,
        required=True,
        help="API key index (2-254 per Lighter docs)",
    )
    parser.add_argument(
        "--expiry-seconds",
        type=int,
        default=3600,
        help="Token expiry in seconds (default: %(default)s)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)

    async def _run():
        signer = SignerClient(
            url=args.base_url,
            private_key=args.api_key_private_key,
            account_index=args.account_index,
            api_key_index=args.api_key_index,
        )
        try:
            token, err = signer.create_auth_token_with_expiry(deadline=args.expiry_seconds)
            if err:
                raise RuntimeError(err)
            print(token)
        finally:
            await signer.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
