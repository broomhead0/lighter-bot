import asyncio
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class HedgerDryRun:
    """Simulates fills received from MakerEngine."""
    def __init__(self, state):
        self.state = state
        self.running = True

    async def run(self):
        logger.info("HedgerDryRun started.")
        while self.running:
            fill = await self.state.pop_fill()
            pair, side, price, size = fill
            self.state.record_fill(pair, side, price, size)
            logger.info(f"[hedger] applied fill {side} {size}@{price} on {pair}")
