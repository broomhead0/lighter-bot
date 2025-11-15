#!/usr/bin/env python3
"""
Query ALL trades from Lighter API (with pagination support).

This script uses the same approach as fetch_trades.py but fetches ALL trades
by paginating through the API. Uses refresh_ws_token.py to generate a fresh
token if needed, or falls back to LIGHTER_API_BEARER env var.

Usage:
    python scripts/query_api_history_v2.py --output data/metrics/fills_api.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"

# Try importing yaml (optional - can use env vars instead)
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_config(path: Path) -> Dict[str, Any]:
    if not HAS_YAML or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def generate_fresh_token() -> Optional[str]:
    """Generate a fresh token using SignerClient directly or refresh_ws_token.py."""
    # Try direct import first (if lighter-python is installed)
    try:
        # Try common user site-packages paths
        import sys
        import os
        user_site = os.path.expanduser("~/.local/lib/python3.11/site-packages")
        if os.path.exists(user_site):
            sys.path.insert(0, user_site)
        
        from lighter import SignerClient
        
        print("  ✅ SignerClient imported directly, generating token...")
        
        async def _generate():
            base_url = os.getenv("API_BASE_URL", "https://mainnet.zklighter.elliot.ai")
            api_key = os.getenv("API_KEY_PRIVATE_KEY", "")
            account_index = int(os.getenv("ACCOUNT_INDEX") or os.getenv("API_ACCOUNT_INDEX") or 366110)
            api_key_index = int(os.getenv("API_KEY_INDEX", "3"))
            
            signer = SignerClient(
                url=base_url,
                private_key=api_key,
                account_index=account_index,
                api_key_index=api_key_index,
            )
            try:
                token, err = signer.create_auth_token_with_expiry(deadline=3600)
                if err:
                    raise RuntimeError(err)
                return token
            finally:
                await signer.close()
        
        token = asyncio.run(_generate())
        print(f"✅ Generated fresh token via SignerClient: {token[:30]}...")
        return token
        
    except ImportError:
        print("  ⚠️  lighter-python not available for direct import, trying refresh_ws_token.py...")
    
    # Fallback: Try refresh_ws_token.py script
    try:
        script_path = Path(__file__).parent / "refresh_ws_token.py"
        if not script_path.exists():
            return None
        
        print("  Generating fresh token using refresh_ws_token.py...")
        result = subprocess.run(
            [sys.executable, str(script_path), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            # Extract token from output
            for line in result.stdout.split("\n"):
                if line.startswith("WS token:"):
                    token = line.split("WS token:")[1].strip()
                    print(f"✅ Generated fresh token via refresh_ws_token.py: {token[:30]}...")
                    return token
        
        print(f"  ⚠️  refresh_ws_token.py failed: {result.stderr[:200]}")
        return None
    except Exception as e:
        print(f"  ⚠️  Could not generate token: {e}")
        return None


async def fetch_all_trades(
    base_url: str,
    account_index: int,
    bearer_token: str,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch ALL trades by paginating through the API."""
    url = f"{base_url.rstrip('/')}/api/v1/trades"
    all_trades = []
    offset = 0

    print(f"Fetching trades from {url}...")
    print(f"Account: {account_index}, Limit per page: {limit}")
    print()

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            params = {
                "account_index": account_index,
                "sort_by": "timestamp",
                "sort_dir": "desc",
                "limit": limit,
                "auth": bearer_token,
            }

            # Try adding offset for pagination (if supported)
            if offset > 0:
                params["offset"] = offset

            try:
                print(f"Fetching page {offset // limit + 1} (offset={offset})...", end=" ")
                resp = await client.get(url, params=params)

                if resp.status_code == 401:
                    print(f"\n❌ Unauthorized (401) - token is expired")
                    print(f"   Response: {resp.text[:200]}")
                    print(f"\n💡 Solution: Generate a fresh token:")
                    print(f"   1. Run locally (where lighter-python is installed):")
                    print(f"      python3 scripts/refresh_ws_token.py")
                    print(f"   2. Update Railway env var:")
                    print(f"      railway variables --set LIGHTER_API_BEARER=<fresh_token>")
                    print(f"   3. Or run this script with --token <fresh_token>")
                    break
                elif resp.status_code != 200:
                    print(f"\n❌ Error {resp.status_code}: {resp.text[:200]}")
                    break

                data = resp.json()
                trades = data.get("trades") if isinstance(data, dict) else data

                if not isinstance(trades, list):
                    print(f"\n❌ Unexpected response format: {type(trades)}")
                    break

                if len(trades) == 0:
                    print("(no more trades)")
                    break

                all_trades.extend(trades)
                print(f"✅ Got {len(trades)} trades (total: {len(all_trades)})")

                # Check if we got fewer than limit (end of data)
                if len(trades) < limit:
                    print(f"(Received {len(trades)} < limit {limit}, reached end)")
                    break

                # For next page, try increasing offset
                # Note: API might not support offset, in which case we'd need cursor-based pagination
                offset += limit

                # Safety limit: stop after 1000 trades (10 pages with limit=100)
                if len(all_trades) >= 1000:
                    print(f"\n⚠️  Reached safety limit of 1000 trades. Stopping.")
                    print(f"   (This might not be all trades - API may not support pagination)")
                    break

            except Exception as e:
                print(f"\n❌ Error fetching page: {e}")
                break

    return all_trades


async def main() -> None:
    parser = argparse.ArgumentParser(description="Query ALL trades from Lighter API")
    parser.add_argument("--output", type=Path, default="data/metrics/fills_api.jsonl", help="Output file")
    parser.add_argument("--token", type=str, help="Bearer token (falls back to LIGHTER_API_BEARER or generates fresh)")
    parser.add_argument("--base-url", type=str, help="Override API base URL")
    parser.add_argument("--account", type=str, help="Override account identifier")
    parser.add_argument("--limit", type=int, default=100, help="Trades per page (default: 100)")
    args = parser.parse_args()

    # Load config (optional - can use env vars)
    cfg = load_config(CONFIG_PATH)
    api_cfg = cfg.get("api") or {}

    base_url = (
        args.base_url
        or os.getenv("API_BASE_URL")
        or api_cfg.get("base_url")
        or "https://mainnet.zklighter.elliot.ai"
    )

    # Get account from args, env var, or config
    account = (
        args.account
        or os.getenv("ACCOUNT_INDEX")
        or os.getenv("API_ACCOUNT_INDEX")
        or api_cfg.get("account_index")
    )

    if account is None:
        raise SystemExit(
            "Account identifier missing. "
            "Set ACCOUNT_INDEX env var, api.account_index in config.yaml, or pass --account."
        )
    account_index = int(account)

    # Get bearer token - always try to generate fresh first, then fall back to provided/env var
    print("Attempting to generate fresh auth token...")
    bearer_token = generate_fresh_token()
    
    # If generation failed, fall back to provided token or env var
    if not bearer_token:
        print("Token generation failed, using provided token or LIGHTER_API_BEARER env var...")
        bearer_token = args.token or os.getenv("LIGHTER_API_BEARER")
        
        if not bearer_token:
            raise SystemExit(
                "Missing auth token. Set LIGHTER_API_BEARER env var, "
                "pass --token, or ensure lighter-python is installed to generate a token."
            )
        else:
            print(f"Using provided token: {bearer_token[:30]}...")

    # Fetch all trades
    all_trades = await fetch_all_trades(
        base_url=base_url,
        account_index=account_index,
        bearer_token=bearer_token,
        limit=args.limit,
    )

    if not all_trades:
        print("\n❌ No trades retrieved")
        sys.exit(1)

    # Export to JSONL
    args.output.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with args.output.open("w", encoding="utf-8") as f:
        for trade in all_trades:
            f.write(json.dumps(trade) + "\n")
            count += 1

    print(f"\n✅✅✅ Success! Exported {count} trades to {args.output}")
    print(f"\nNext: Run export_pnl_windows.py on this file for analysis")


if __name__ == "__main__":
    asyncio.run(main())

