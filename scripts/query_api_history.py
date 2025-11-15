#!/usr/bin/env python3
"""Query Lighter API for full trading history.

This script queries the Lighter exchange API to get ALL fills/orders
since account inception, then exports them for analysis.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml

    def load_config():
        """Load config from YAML file."""
        config_path = Path("config.yaml")
        if not config_path.exists():
            config_path = Path(__file__).parent.parent / "config.yaml"
        with config_path.open() as f:
            return yaml.safe_load(f)
except ImportError:
    def load_config():
        return {}


async def query_fills_via_api():
    """Query the API for full fill history."""
    # Prefer Railway env vars (production), fall back to config.yaml
    base_url = os.getenv("API_BASE_URL") or os.getenv("LIGHTER_API_BASE_URL")
    if not base_url:
        cfg = load_config()
        api_cfg = cfg.get("api", {})
        base_url = api_cfg.get("base_url", "http://127.0.0.1:8787")

    base_url = base_url.rstrip("/")

    account_index = int(os.getenv("API_ACCOUNT_INDEX") or
                       os.getenv("ACCOUNT_INDEX") or
                       load_config().get("api", {}).get("account_index", 366110))

    # Always generate a fresh token (tokens expire after 1 hour)
    # This ensures we have a valid token for each API request
    # Use the same approach as refresh_ws_token.py
    bearer_token = None
    api_key = os.getenv("API_KEY_PRIVATE_KEY", "")
    api_key_index = int(os.getenv("API_KEY_INDEX", "3"))
    
    if not api_key:
        print("⚠️  API_KEY_PRIVATE_KEY not set - cannot generate auth token")
        bearer_token = os.getenv("LIGHTER_API_BEARER", "")
        if bearer_token:
            print("  Using LIGHTER_API_BEARER from environment (may be expired)")
    else:
        print("Generating fresh auth token...")
        try:
            # Try importing lighter the same way refresh_ws_token.py does
            # This is the most reliable method since refresh_ws_token.py works
            from lighter import SignerClient  # type: ignore
            
            print("  ✅ SignerClient imported successfully")
            
            async def generate_token():
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
            
            token = await generate_token()
            bearer_token = token
            print(f"✅ Generated fresh auth token: {token[:30]}...")
            
        except ImportError as e:
            print(f"⚠️  lighter-python not available: {e}")
            print("  Falling back to LIGHTER_API_BEARER from environment (may be expired)")
            # Fallback to env var if available
            bearer_token = os.getenv("LIGHTER_API_BEARER", "")
            if bearer_token:
                print(f"  Using LIGHTER_API_BEARER: {bearer_token[:30]}...")
            else:
                print("  ❌ Cannot proceed without token generation or LIGHTER_API_BEARER")
        except Exception as e:
            print(f"⚠️  Could not generate token: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to env var if available
            bearer_token = os.getenv("LIGHTER_API_BEARER", "")
            if bearer_token:
                print(f"  Falling back to LIGHTER_API_BEARER: {bearer_token[:30]}...")

    print(f"Querying Lighter API: {base_url}")
    print(f"Account: {account_index}")
    print()

    if not bearer_token:
        print("⚠️  No bearer token found. Trying unauthenticated endpoints...")

    # Common endpoints for order/fill history
    endpoints = [
        # Standard REST API patterns
        f"/api/v1/account/{account_index}/orders",
        f"/api/v1/account/{account_index}/fills",
        f"/api/v1/account/{account_index}/trades",
        f"/api/v1/orders?account={account_index}",
        f"/api/v1/fills?account={account_index}",
        # Trades endpoint (like fetch_trades.py - uses account_index and auth in query params)
        f"/api/v1/trades",  # Will add params separately with auth
        # Alternative patterns
        f"/api/account/{account_index}/orders",
        f"/api/account/{account_index}/fills",
        f"/account/{account_index}/orders",
        f"/account/{account_index}/fills",
    ]

    headers = {}
    # fetch_trades.py uses 'auth' as a query parameter, not a header!
    # So we'll add auth to query params, not headers

    # Try REST API directly (use httpx which is in requirements.txt)
    try:
        import httpx
        use_httpx = True
    except ImportError:
        try:
            import aiohttp
            use_httpx = False
        except ImportError:
            print("ERROR: Neither httpx nor aiohttp installed")
            return None

    if use_httpx:
        # Use httpx (synchronous but simpler)
        print("Using httpx for API calls...")
        client = httpx.Client(timeout=30.0, follow_redirects=True)
        try:
            # Try /api/v1/trades with auth in query params (like fetch_trades.py)
            if bearer_token:
                url = f"{base_url}/api/v1/trades"
                # fetch_trades.py uses account_index (not account!) and auth as query params
                params_trades = {
                    "account_index": account_index,
                    "sort_by": "timestamp",
                    "sort_dir": "desc",
                    "limit": 100,  # fetch_trades.py uses 100-200
                    "auth": bearer_token,
                }
                print(f"Trying: {url} with auth token")

                resp = client.get(url, params=params_trades, headers=headers)
                print(f"  Status: {resp.status_code}")

                if resp.status_code == 200:
                    data = resp.json()
                    # Check if it's wrapped
                    trades = data.get("trades") if isinstance(data, dict) else data
                    if trades is None:
                        trades = data if isinstance(data, list) else []

                    count = len(trades) if isinstance(trades, list) else 1
                    print(f"  ✅ Success! Got {count} items")

                    if isinstance(trades, list) and len(trades) > 0:
                        print(f"  ✅ Looks like trade data!")
                        return trades
                elif resp.status_code == 400:
                    print(f"  ❌ Error: {resp.text[:200]}")

            # Try other endpoints (without auth for now)
            for endpoint in endpoints:
                if "/api/v1/trades" in endpoint:
                    continue  # Already tried above

                try:
                    url = f"{base_url}{endpoint}"
                    print(f"Trying: {url}")

                    resp = client.get(url, headers=headers)
                    print(f"  Status: {resp.status_code}")

                    if resp.status_code == 200:
                        data = resp.json()
                        count = len(data) if isinstance(data, list) else 1
                        print(f"  ✅ Success! Got {count} items")

                        # Check if it's the right format
                        if isinstance(data, list) and len(data) > 0:
                            first = data[0]
                            if any(key in first for key in ["fill", "trade", "order", "timestamp", "price", "size"]):
                                print(f"  ✅ Looks like fill/order data!")
                                # If pagination is possible, try to get more
                                if len(data) >= 1000:  # Might be more pages
                                    print(f"  ⚠️  Got {len(data)} items - might need pagination for full history")
                                return data
                        elif isinstance(data, dict):
                            # Might be paginated or wrapped
                            if "data" in data:
                                items = data["data"]
                                if isinstance(items, list) and len(items) > 0:
                                    print(f"  ✅ Got wrapped data with {len(items)} items")
                                    # Check for pagination info
                                    if "has_more" in data or "next_offset" in data:
                                        print(f"  ⚠️  Pagination available - may need to fetch more pages")
                                    return items
                        elif isinstance(data, dict):
                            # Might be paginated or wrapped
                            if "data" in data:
                                items = data["data"]
                                if isinstance(items, list) and len(items) > 0:
                                    print(f"  ✅ Got wrapped data with {len(items)} items")
                                    return items
                    elif resp.status_code == 401:
                        print(f"  ⚠️  Unauthorized - might need API key")
                    elif resp.status_code == 404:
                        print(f"  ❌ Not found")
                    else:
                        print(f"  ❌ Error: {resp.text[:200]}")
                except Exception as e:
                    print(f"  ❌ Failed: {e}")
        finally:
            client.close()
    else:
        # Use aiohttp (async) - fallback
        print("Using aiohttp for API calls...")
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    print(f"Trying: {url}")

                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        print(f"  Status: {resp.status}")

                        if resp.status == 200:
                            data = await resp.json()
                            count = len(data) if isinstance(data, list) else 1
                            print(f"  ✅ Success! Got {count} items")

                            if isinstance(data, list) and len(data) > 0:
                                first = data[0]
                                if any(key in first for key in ["fill", "trade", "order", "timestamp", "price", "size"]):
                                    print(f"  ✅ Looks like fill/order data!")
                                    return data
                        elif resp.status == 401:
                            print(f"  ⚠️  Unauthorized - might need API key")
                        elif resp.status == 404:
                            print(f"  ❌ Not found")
                        else:
                            text = await resp.text()
                            print(f"  ❌ Error: {text[:200]}")
                except asyncio.TimeoutError:
                    print(f"  ⏱️  Timeout")
                except Exception as e:
                    print(f"  ❌ Failed: {e}")

    # Try using SignerClient if available (this is most likely to work!)
    print("\nTrying SignerClient methods...")
    if not api_key:
        print("  ⚠️  No API key - cannot use SignerClient")
    else:
        try:
            import lighter
            from lighter import SignerClient

            print(f"Creating SignerClient with:")
            print(f"  URL: {base_url}")
            print(f"  Account: {account_index}")
            print(f"  API Key Index: 3")

            client = SignerClient(
                url=base_url,
                private_key=api_key,
                account_index=account_index,
                api_key_index=3,
                nonce_management_type=lighter.nonce_manager.NonceManagerType.OPTIMISTIC,
            )

            # Check available methods
            methods = [m for m in dir(client) if not m.startswith("_")]
            print(f"\nAvailable methods: {len(methods)}")

            # Look for history-related methods
            history_methods = [m for m in methods if any(
                term in m.lower() for term in ["order", "fill", "trade", "history", "account", "position", "query"]
            )]
            print(f"History-related methods: {history_methods[:10]}")

            # Try methods that might get history
            for method_name in history_methods[:10]:  # Limit to first 10
                try:
                    method = getattr(client, method_name)
                    if not callable(method):
                        continue

                    print(f"\nTrying {method_name}...")

                    # Try calling with common parameters
                    try:
                        if asyncio.iscoroutinefunction(method):
                            # Try different signatures
                            try:
                                result = await method()  # No args
                            except:
                                try:
                                    result = await method(account_index=account_index)  # With account
                                except:
                                    result = await method(account=account_index)
                        else:
                            try:
                                result = method()  # No args
                            except:
                                try:
                                    result = method(account_index=account_index)  # With account
                                except:
                                    result = method(account=account_index)

                        if result and (isinstance(result, list) and len(result) > 0) or (isinstance(result, dict) and result):
                            print(f"  ✅ Got result from {method_name}: {len(result) if isinstance(result, list) else 'dict'}")
                            if isinstance(result, list) and len(result) > 0:
                                print(f"  Sample item keys: {list(result[0].keys())[:5] if isinstance(result[0], dict) else 'N/A'}")
                            return result
                        else:
                            print(f"  ⚠️  Empty result")
                    except TypeError:
                        print(f"  ⚠️  Wrong signature - skipping")
                except Exception as e:
                    print(f"  ❌ {method_name} failed: {e}")

            await client.close()
        except ImportError:
            print("  lighter-python not available")
        except Exception as e:
            print(f"  SignerClient failed: {e}")

    print("\n❌ Could not retrieve history via API")
    print("\nNext steps:")
    print("  1. Check Lighter API documentation for order/fill endpoints")
    print("  2. Contact exchange support for historical data access")
    print("  3. Use position updates (realized_pnl) from WebSocket as source of truth")

    return None


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Query full fill history from API")
    parser.add_argument("--output", type=Path, default="data/metrics/fills_api.jsonl", help="Output file")

    args = parser.parse_args()

    result = asyncio.run(query_fills_via_api())

    if result:
        # Export to JSONL format
        args.output.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with args.output.open("w") as f:
            if isinstance(result, list):
                for item in result:
                    f.write(json.dumps(item) + "\n")
                    count += 1
            else:
                f.write(json.dumps(result) + "\n")
                count = 1

        print(f"\n✅ Exported {count} items to {args.output}")
        print(f"\nNext: Run export_pnl_windows.py on this file")
    else:
        print("\n❌ Could not retrieve history from API")
        print("\nNote: You may need to:")
        print("  1. Check Lighter API documentation")
        print("  2. Ensure API key is configured")
        print("  3. Check if historical data is available via API")
        sys.exit(1)


if __name__ == "__main__":
    main()
