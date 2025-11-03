from __future__ import annotations
import json
import time
from typing import Callable, Iterable

def iter_jsonl(path: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                # skip malformed
                continue

def replay_jsonl(path: str, on_frame: Callable[[dict], None], speed: float = 1.0):
    """
    Replays frames from a JSONL capture at `speed` multiplier.
    If frames lack timestamps, we just stream them at ~50 fps / speed.
    """
    delay = max(0.0, 0.02 / max(1e-9, speed))  # default ~50 fps
    for frame in iter_jsonl(path):
        on_frame(frame)
        time.sleep(delay)
