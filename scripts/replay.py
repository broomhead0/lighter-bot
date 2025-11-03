from __future__ import annotations
import argparse
import os

from modules.raw_replayer import replay_jsonl
from modules.message_router import MessageRouter
from core.logger import logger

def main():
    ap = argparse.ArgumentParser(description="Replay captured WS frames from JSONL")
    ap.add_argument("--file", default="logs/ws_raw.jsonl", help="Path to capture JSONL")
    ap.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier")
    args = ap.parse_args()

    router = MessageRouter()

    def on_connected(frame: dict):
        logger.info(f"[REPLAY] CONNECTED session_id={frame.get('session_id','')}")

    def on_height(frame: dict):
        h = frame.get("height")
        logger.info(f"[REPLAY] HEIGHT {h}")

    def on_market_stats(frame: dict):
        # Compact view of a couple of markets if present
        ms = frame.get("market_stats", {})
        # print BTC (1) and ETH (0) if present
        for k in ("0", "1", 0, 1):
            m = ms.get(k)
            if m:
                logger.info(f"[REPLAY] MARKET {m.get('market_id')} mark={m.get('mark_price')} "
                            f"idx={m.get('index_price')} fr={m.get('funding_rate')} "
                            f"oi={m.get('open_interest')} ")

    def on_error(frame: dict):
        logger.error(f"[REPLAY] ERROR <- {frame}")

    router.on("connected", on_connected)
    router.on("update/height", on_height)
    router.on("update/market_stats", on_market_stats)
    router.on("error", on_error)

    def route(frame: dict):
        t = frame.get("type", "")
        fn = router._handlers.get(t)
        if fn:
            try:
                fn(frame)
            except Exception as e:
                logger.error(f"[REPLAY] Handler error for {t}: {e}")
        else:
            logger.info(f"[REPLAY] UNHANDLED <- {str(frame)[:300]}")

    logger.info(f"Replaying {args.file} at {args.speed}x ...")
    replay_jsonl(args.file, route, speed=args.speed)
    logger.info("Replay complete.")

if __name__ == "__main__":
    main()
