#!/usr/bin/env python3
"""Query Lighter API for full trading history.

This script queries the Lighter exchange API to get ALL fills/orders
since account inception, then exports them for analysis.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
    from pathlib import Path as PathLib
    
    def load_config():
        """Load config from YAML file."""
        config_path = PathLib("config.yaml")
        if not config_path.exists():
            config_path = PathLib(__file__).parent.parent / "config.yaml"
        with config_path.open() as f:
            return yaml.safe_load(f)
except ImportError:
    def load_config():
        return {}


async def query_fills_via_api():
    """Query the API for full fill history."""
    cfg = load_config()
    api_cfg = cfg.get("api", {})
    
    base_url = api_cfg.get("base_url", "http://127.0.0.1:8787").rstrip("/")
    account_index = int(api_cfg.get("account_index", 366110))
    api_key = api_cfg.get("key", "")
    
    print(f"Querying Lighter API: {base_url}")
    print(f"Account: {account_index}")
    print()
    
    if not api_key:
        print("⚠️  No API key found. Trying unauthenticated endpoints...")
    
    # Try REST API directly with aiohttp
    try:
        import aiohttp
    except ImportError:
        print("ERROR: aiohttp not installed")
        return None
    
    async with aiohttp.ClientSession() as session:
        # Common endpoints for order/fill history
        endpoints = [
            # Standard REST API patterns
            f"/api/v1/account/{account_index}/orders",
            f"/api/v1/account/{account_index}/fills",
            f"/api/v1/account/{account_index}/trades",
            f"/api/v1/orders?account={account_index}",
            f"/api/v1/fills?account={account_index}",
            f"/api/v1/trades?account={account_index}",
            # Alternative patterns
            f"/api/account/{account_index}/orders",
            f"/api/account/{account_index}/fills",
            f"/account/{account_index}/orders",
            f"/account/{account_index}/fills",
        ]
        
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["X-API-KEY"] = api_key
        
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
                        
                        # Check if it's the right format
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
    
    # Try using SignerClient if available
    print("\nTrying SignerClient methods...")
    try:
        import lighter
        from lighter import SignerClient
        
        client = SignerClient(
            url=base_url,
            private_key=api_key if api_key else "0x0",
            account_index=account_index,
            api_key_index=3,
            nonce_management_type=lighter.nonce_manager.NonceManagerType.OPTIMISTIC,
        )
        
        # Check available methods
        methods = [m for m in dir(client) if not m.startswith("_")]
        print(f"Available methods: {len(methods)}")
        
        # Try methods that might get history
        for method_name in ["get_orders", "get_fills", "get_trades", "query_orders", "get_account"]:
            if hasattr(client, method_name):
                try:
                    method = getattr(client, method_name)
                    print(f"Trying {method_name}...")
                    if asyncio.iscoroutinefunction(method):
                        result = await method()
                    else:
                        result = method()
                    
                    if result:
                        print(f"  ✅ Got result from {method_name}")
                        return result
                except Exception as e:
                    print(f"  ❌ {method_name} failed: {e}")
        
        await client.close()
    except ImportError:
        print("  lighter-python not available locally")
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

