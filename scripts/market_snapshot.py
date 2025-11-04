from __future__ import annotations
import argparse
import json
from modules.raw_replayer import iter_jsonl


def main():
    ap = argparse.ArgumentParser(
        description="Extract latest market stats for select markets"
    )
    ap.add_argument("--file", default="logs/ws_raw.jsonl")
    ap.add_argument("--markets", default="0,1", help="Comma list of market ids")
    args = ap.parse_args()

    want = set(x.strip() for x in args.markets.split(","))
    latest = {}

    for frame in iter_jsonl(args.file):
        if frame.get("type") != "update/market_stats":
            continue
        ms = frame.get("market_stats", {})
        for k, v in ms.items():
            if str(k) in want:
                latest[str(k)] = v

    print(json.dumps(latest, indent=2))


if __name__ == "__main__":
    main()
