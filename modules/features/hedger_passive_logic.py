from __future__ import annotations

"""
Hedger Passive Logic Feature Module (stub)

Extracted from hedger.py to allow independent enable/disable.
Attempts passive fills first, falls back to active if timeout.

Phase 0 note: Provide interface; integration into hedger will be done later.
"""

import asyncio
from typing import Optional


class HedgerPassiveLogic:
    def __init__(self, config: dict, trading_client):
        self.enabled = bool((config or {}).get("enabled", False))
        self.wait_seconds = float((config or {}).get("passive_wait_seconds", 0.5))
        self.offset_bps = float((config or {}).get("passive_offset_bps", 2.0))
        self.timeout_seconds = float((config or {}).get("passive_timeout_seconds", 6.0))
        self.trading = trading_client

    async def try_passive_fill(self, market: str, side: str, size: float, mid: float) -> bool:
        if not self.enabled or self.trading is None:
            return False
        # Phase 0: stub returns False (caller should proceed with normal path)
        await asyncio.sleep(0)
        return False
