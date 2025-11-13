#!/usr/bin/env python3
"""
Quick regime analysis check: compare internal vs external volatility and run regime analysis.
"""
import json
import requests
import sys
from pathlib import Path
from datetime import datetime, timezone
import time

def fetch_sol_candles():
    """Fetch recent SOL/USDT candles from Binance."""
    now = int(time.time() * 1000)
    start_time = now - (24 * 60 * 60 * 1000)
    
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": "SOLUSDT",
        "interval": "1m",
        "startTime": start_time,
        "limit": 1440
    }
    
    print("Fetching SOL/USDT candles from Binance...")
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch candles: {resp.status_code}")
        return None
    
    candles_raw = resp.json()
    candles = []
    for c in candles_raw:
        candles.append({
            "open_time": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        })
    
    output_path = Path("data/analysis/binance_solusdt_1m_recent.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(candles, f, indent=2)
    
    print(f"✅ Saved {len(candles)} candles to {output_path}")
    return candles

def calc_volatility(candles, window_minutes=60):
    """Calculate volatility from candles."""
    if len(candles) < window_minutes:
        return None
    
    recent = candles[-window_minutes:]
    returns = []
    for i in range(1, len(recent)):
        prev_close = recent[i-1]["close"]
        curr_close = recent[i]["close"]
        if prev_close > 0:
            ret = abs((curr_close - prev_close) / prev_close)
            returns.append(ret)
    
    if not returns:
        return None
    
    avg_return = sum(returns) / len(returns)
    vol_bps = avg_return * 10000
    return vol_bps

def main():
    candles = fetch_sol_candles()
    if not candles:
        return 1
    
    # Calculate volatility
    vol_60m = calc_volatility(candles, 60)
    vol_15m = calc_volatility(candles, 15)
    
    print("\n=== VOLATILITY COMPARISON ===")
    if vol_60m:
        print(f"External SOL volatility (last 60m): {vol_60m:.2f} bps")
    if vol_15m:
        print(f"External SOL volatility (last 15m): {vol_15m:.2f} bps")
    
    print("\n=== THRESHOLD VALIDATION ===")
    print(f"Low-vol pause threshold: 3.0 bps")
    print(f"Regime switch threshold: 6.0 bps")
    print(f"High-vol pause threshold: 30.0 bps")
    
    if vol_60m:
        if vol_60m < 3.0:
            print(f"✅ External vol ({vol_60m:.2f} bps) aligns with low-vol pause")
        elif vol_60m < 6.0:
            print(f"⚠️  External vol ({vol_60m:.2f} bps) is between pause (3.0) and regime (6.0)")
        elif vol_60m < 30.0:
            print(f"✅ External vol ({vol_60m:.2f} bps) suggests normal trading conditions")
        else:
            print(f"⚠️  External vol ({vol_60m:.2f} bps) exceeds high-vol pause threshold")
    
    print("\n=== NEXT STEPS ===")
    print("1. Check internal bot volatility via metrics")
    print("2. Compare with external volatility above")
    print("3. Run full regime analysis: python analysis/regime_analysis.py")
    print("4. Update findings in CHANGES_SUMMARY.md if thresholds need adjustment")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

