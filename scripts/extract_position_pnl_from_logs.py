#!/usr/bin/env python3
"""Extract position PnL updates from Railway logs for analysis.

This script parses Railway logs to extract position updates with realized_pnl
and unrealized_pnl from the exchange. This is the source of truth that matches UI PnL.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import pytz


def parse_position_updates(log_lines: List[str]) -> List[Tuple[float, str, float, float, float]]:
    """Parse log lines to extract position updates with PnL.
    
    Returns list of (timestamp, market, realized_pnl, unrealized_pnl, total_pnl)
    """
    updates = []
    
    for line in log_lines:
        # Look for position updates with realized_pnl
        if '"realized_pnl"' not in line:
            continue
            
        # Try to extract timestamp from log line
        ts_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
        ts = 0.0
        if ts_match:
            try:
                dt = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
                # Assume UTC if no timezone
                ts = dt.replace(tzinfo=pytz.UTC).timestamp()
            except:
                pass
        
        # Try to parse JSON from line
        try:
            # Find JSON object in line
            match = re.search(r'\{.*"positions".*\}', line)
            if match:
                data = json.loads(match.group())
                positions = data.get("positions", {})
                for market_id, pos in positions.items():
                    rpnl = pos.get("realized_pnl")
                    upnl = pos.get("unrealized_pnl")
                    if rpnl is not None:
                        try:
                            rpnl_val = float(rpnl)
                            upnl_val = float(upnl) if upnl else 0.0
                            total = rpnl_val + upnl_val
                            market = f"market:{market_id}"
                            updates.append((ts, market, rpnl_val, upnl_val, total))
                        except:
                            pass
        except:
            # Try direct extraction if JSON parse fails
            rpnl_match = re.search(r'"realized_pnl"\s*:\s*"?([0-9.-]+)"?', line)
            upnl_match = re.search(r'"unrealized_pnl"\s*:\s*"?([0-9.-]+)"?', line)
            market_match = re.search(r'"market_id"\s*:\s*"?([0-9]+)"?', line)
            
            if rpnl_match:
                try:
                    rpnl_val = float(rpnl_match.group(1))
                    upnl_val = float(upnl_match.group(1)) if upnl_match else 0.0
                    market_id = market_match.group(1) if market_match else "unknown"
                    market = f"market:{market_id}"
                    total = rpnl_val + upnl_val
                    updates.append((ts, market, rpnl_val, upnl_val, total))
                except:
                    pass
    
    # Sort by timestamp
    updates.sort(key=lambda x: x[0])
    return updates


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract position PnL from logs")
    parser.add_argument("--input", type=Path, default="-", help="Input log file (stdin if -)")
    parser.add_argument("--output", type=Path, required=True, help="Output CSV file")
    parser.add_argument("--market", type=str, default="market:2", help="Market to filter")
    
    args = parser.parse_args()
    
    # Read input
    if args.input == Path("-"):
        lines = sys.stdin.readlines()
    else:
        with args.input.open("r") as f:
            lines = f.readlines()
    
    # Parse position updates
    updates = parse_position_updates(lines)
    
    # Filter by market
    if args.market:
        updates = [u for u in updates if u[1] == args.market]
    
    if not updates:
        print("No position updates found!", file=sys.stderr)
        sys.exit(1)
    
    # Write CSV
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        f.write("timestamp,market,realized_pnl,unrealized_pnl,total_pnl\n")
        for ts, market, rpnl, upnl, total in updates:
            dt = datetime.fromtimestamp(ts, tz=pytz.UTC) if ts > 0 else datetime.now(pytz.UTC)
            f.write(f"{int(ts)},{market},{rpnl:.6f},{upnl:.6f},{total:.6f}\n")
    
    print(f"Extracted {len(updates)} position updates")
    if updates:
        latest = updates[-1]
        print(f"Latest: {latest[1]} total_pnl=${latest[4]:.2f}")
        print(f"Wrote to {args.output}")


if __name__ == "__main__":
    main()

