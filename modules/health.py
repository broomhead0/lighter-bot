from __future__ import annotations
import time
from core.logger import logger

class HealthMonitor:
    def __init__(self, max_silence_sec: int = 45, max_reconnects: int = 5, window_sec: int = 300):
        self.max_silence_sec = max_silence_sec
        self.max_reconnects = max_reconnects
        self.window_sec = window_sec
        self._last_msg_t = time.time()
        self._reconnect_timestamps: list[float] = []

    def note_message(self):
        self._last_msg_t = time.time()

    def note_reconnect(self):
        now = time.time()
        self._reconnect_timestamps.append(now)
        # Evict old
        cutoff = now - self.window_sec
        self._reconnect_timestamps = [t for t in self._reconnect_timestamps if t >= cutoff]

    def check(self):
        now = time.time()
        if now - self._last_msg_t > self.max_silence_sec:
            logger.warning(f"[HEALTH] No messages for {int(now - self._last_msg_t)}s (> {self.max_silence_sec}s)")
            self._last_msg_t = now  # avoid spamming every tick

        if len(self._reconnect_timestamps) > self.max_reconnects:
            logger.warning(f"[HEALTH] Reconnects in last {self.window_sec}s = {len(self._reconnect_timestamps)} "
                           f"(> {self.max_reconnects})")
            # keep timestamps; caller may decide to kill or alert externally
