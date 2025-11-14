#!/usr/bin/env python3
"""Quick performance check since deploy."""
import csv
import sys
from datetime import datetime, timezone

deploy_ts_ms = 1763064363565.0

print("=== PERFORMANCE SINCE DEPLOY ===")
try:
    with open("/tmp/pnl_since_deploy.csv") as fh:
        rdr = csv.DictReader(fh)
        rows = list(rdr)
        if rows:
            for row in rows:
                start_ts = float(row["bucket_start_ts"])
                dt = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
                realized = float(row["realized_quote"])
                base_delta = float(row["base_delta"])
                maker_vol = float(row["maker_volume"])
                taker_vol = float(row["taker_volume"])

                print(f"Window: {dt.strftime('%H:%M:%S')}")
                print(f"  Realized: ${realized:.2f}")
                print(f"  Base delta: {base_delta:.4f} SOL")
                print(f"  Maker volume: ${maker_vol:.2f}")
                print(f"  Taker volume: ${taker_vol:.2f}")
        else:
            print("No windows found")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

