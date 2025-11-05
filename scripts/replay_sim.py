# scripts/replay_sim.py
"""
Replay simulator for M8: reads captured WS frames from logs/ws_raw.jsonl
and replays them through the message router at configurable speed.
"""
import asyncio
import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set

LOG = logging.getLogger("replay")


class ReplaySimulator:
    """
    Replays captured WS frames from JSONL file.

    Expected format per line: {"ts": timestamp, "raw": "json_string"}
    Or legacy: just the raw JSON string (no wrapper).
    """

    def __init__(
        self,
        path: str,
        router: Callable[[str], None],
        speed: float = 1.0,
        market_filter: Optional[List[str]] = None,
        telemetry=None,
        chaos_injector=None,
    ):
        self.path = path
        self.router = router
        self.speed = max(0.01, float(speed))  # clamp to reasonable range
        self.market_filter: Optional[Set[str]] = (
            set(market_filter) if market_filter else None
        )
        self.telemetry = telemetry
        self.chaos = chaos_injector

        # Metrics
        self.frames_processed = 0
        self.frames_dropped = 0
        self.synthetic_frames = 0
        self.real_frames = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.first_ts: Optional[float] = None
        self.last_ts: Optional[float] = None

    async def run(self):
        """Replay frames from file, respecting speed multiplier."""
        if not os.path.exists(self.path):
            LOG.error("[replay] file not found: %s", self.path)
            return

        LOG.info(
            "[replay] starting replay from %s (speed=%.2fx, filter=%s)",
            self.path,
            self.speed,
            self.market_filter,
        )

        self.start_time = time.time()
        prev_ts: Optional[float] = None

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # Try parsing as wrapped format: {"ts": ..., "raw": ...}
                        frame_wrapper = json.loads(line)
                        if isinstance(frame_wrapper, dict) and "raw" in frame_wrapper:
                            frame_ts = frame_wrapper.get("ts")
                            raw_text = frame_wrapper["raw"]
                            is_wrapped = True
                        else:
                            # Legacy: assume it's the raw JSON string itself
                            frame_ts = None
                            raw_text = line
                            is_wrapped = False
                    except json.JSONDecodeError:
                        LOG.debug("[replay] line %d: invalid JSON, skipping", line_num)
                        self.frames_dropped += 1
                        continue

                    # Track timestamps
                    if frame_ts is not None:
                        if self.first_ts is None:
                            self.first_ts = frame_ts
                        self.last_ts = frame_ts

                    # Market filtering (if enabled)
                    if self.market_filter and not self._passes_market_filter(raw_text):
                        self.frames_dropped += 1
                        continue

                    # Replay timing: if we have timestamps, respect them
                    if prev_ts is not None and frame_ts is not None:
                        delay = (frame_ts - prev_ts) / self.speed
                        if delay > 0:
                            await asyncio.sleep(delay)
                    elif prev_ts is None and frame_ts is not None:
                        # First frame with timestamp: no delay
                        pass
                    else:
                        # No timestamps: use default frame rate
                        await asyncio.sleep(0.02 / self.speed)

                    # Inject latency chaos if enabled
                    if self.chaos:
                        await self.chaos.inject_latency(frame_count=1)

                    # Route the frame
                    try:
                        self.router(raw_text)
                        self.frames_processed += 1

                        # Detect synthetic vs real (heuristic: synthetic usually has channel/timestamp structure)
                        if is_wrapped:
                            self.real_frames += 1
                        else:
                            # Check if it looks like a synthetic frame
                            try:
                                parsed = json.loads(raw_text)
                                if isinstance(parsed, dict) and "channel" in parsed:
                                    self.real_frames += 1
                                else:
                                    self.synthetic_frames += 1
                            except Exception:
                                self.real_frames += 1

                        # Touch telemetry if available
                        if self.telemetry:
                            try:
                                self.telemetry.touch("ws")
                            except Exception:
                                pass

                    except Exception as e:
                        LOG.debug("[replay] router error on line %d: %s", line_num, e)
                        self.frames_dropped += 1

                    prev_ts = frame_ts

        except Exception as e:
            LOG.error("[replay] error during replay: %s", e)
            raise
        finally:
            self.end_time = time.time()
            self._log_summary()

    def _passes_market_filter(self, raw_text: str) -> bool:
        """Check if frame contains any market from filter."""
        if not self.market_filter:
            return True
        try:
            parsed = json.loads(raw_text)
            # Check various places where market_id might appear
            if isinstance(parsed, dict):
                # Check data array
                data = parsed.get("data")
                if isinstance(data, list):
                    for item in data:
                        market_id = (
                            item.get("market_id")
                            or item.get("marketId")
                            or item.get("market")
                            or item.get("id")
                        )
                        if market_id and str(market_id) in self.market_filter:
                            return True
                # Check market_stats
                market_stats = parsed.get("market_stats")
                if isinstance(market_stats, list):
                    for item in market_stats:
                        market_id = (
                            item.get("market_id")
                            or item.get("marketId")
                            or item.get("market")
                            or item.get("id")
                        )
                        if market_id and str(market_id) in self.market_filter:
                            return True
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        market_id = (
                            item.get("market_id")
                            or item.get("marketId")
                            or item.get("market")
                            or item.get("id")
                        )
                        if market_id and str(market_id) in self.market_filter:
                            return True
        except Exception:
            pass
        return False

    def _log_summary(self):
        """Log replay summary metrics."""
        duration = (
            (self.end_time - self.start_time) if self.end_time and self.start_time else 0.0
        )
        ts_span = (
            (self.last_ts - self.first_ts) if self.last_ts and self.first_ts else None
        )

        LOG.info("[replay] === REPLAY SUMMARY ===")
        LOG.info("[replay] frames_processed: %d", self.frames_processed)
        LOG.info("[replay] frames_dropped: %d", self.frames_dropped)
        LOG.info("[replay] real_frames: %d", self.real_frames)
        LOG.info("[replay] synthetic_frames: %d", self.synthetic_frames)
        LOG.info("[replay] wall_duration: %.2fs", duration)
        if ts_span:
            LOG.info("[replay] captured_timespan: %.2fs", ts_span)
            LOG.info("[replay] speedup: %.2fx", ts_span / duration if duration > 0 else 0.0)
        LOG.info("[replay] ======================")

    def get_metrics(self) -> Dict[str, Any]:
        """Return metrics dictionary."""
        duration = (
            (self.end_time - self.start_time) if self.end_time and self.start_time else 0.0
        )
        ts_span = (
            (self.last_ts - self.first_ts) if self.last_ts and self.first_ts else None
        )
        return {
            "frames_processed": self.frames_processed,
            "frames_dropped": self.frames_dropped,
            "real_frames": self.real_frames,
            "synthetic_frames": self.synthetic_frames,
            "wall_duration": duration,
            "captured_timespan": ts_span,
            "speedup": ts_span / duration if ts_span and duration > 0 else None,
        }
