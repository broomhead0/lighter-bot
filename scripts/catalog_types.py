from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from modules.raw_replayer import iter_jsonl

def main():
    ap = argparse.ArgumentParser(description="Catalog message types and keys")
    ap.add_argument("--file", default="logs/ws_raw.jsonl")
    args = ap.parse_args()

    type_counts = Counter()
    key_counts = defaultdict(Counter)

    for frame in iter_jsonl(args.file):
        t = frame.get("type", "<none>")
        type_counts[t] += 1
        for k in frame.keys():
            key_counts[t][k] += 1

    print("=== Type Counts ===")
    for t, c in type_counts.most_common():
        print(f"{t:24s} {c}")

    print("\n=== Keys Per Type (top 12) ===")
    for t in type_counts:
        print(f"\n[{t}]")
        for k, c in key_counts[t].most_common(12):
            print(f"  {k:20s} {c}")

if __name__ == "__main__":
    main()
