import asyncio
import logging
import random
from decimal import Decimal, getcontext

# extra precision so tiny bps steps don't underflow
getcontext().prec = 28

class SyntheticMidFeeder:
    """
    Robust synthetic mid-price feeder.
    Accepts cfg with optional keys:
      - pair OR market (string) → defaults to "market:1"
      - start_price (number)    → defaults to 1000
      - vol_bps (float)         → defaults to 3.0
      - drift_bps (float)       → defaults to 0.0
      - mean_revert_bps (float) → defaults to 0.0
      - mean_target (number)    → defaults to start_price
      - interval_ms (int)       → defaults to 1000
    """

    def __init__(self, state, cfg=None):
        self.state = state
        self.cfg = cfg or {}
        self.logger = logging.getLogger("feeder")

        # --- Pair normalization ---
        pair = self.cfg.get("pair") or self.cfg.get("market") or "market:1"
        if not isinstance(pair, str) or not pair.strip():
            pair = "market:1"
        self.pair = pair

        # --- Price process parameters (as Decimals) ---
        self.mid = Decimal(str(self.cfg.get("start_price", 1000)))
        self.vol_bps = Decimal(str(self.cfg.get("vol_bps", 3.0)))
        self.drift_bps = Decimal(str(self.cfg.get("drift_bps", 0.0)))
        self.mean_revert_bps = Decimal(str(self.cfg.get("mean_revert_bps", 0.0)))
        self.mean_target = Decimal(str(self.cfg.get("mean_target", float(self.mid))))
        self.interval_ms = int(self.cfg.get("interval_ms", 1000))

        # --- Ensure state has required attrs ---
        if not hasattr(self.state, "mids"):
            self.state.mids = {}
        if not hasattr(self.state, "last_mid"):
            self.state.last_mid = 0

        self.logger.info(f"[feeder] SyntheticMidFeeder started for {self.pair} from {self.mid}")

    async def run(self):
        while True:
            try:
                # Convert bps to fractional Decimals
                vol = self.vol_bps / Decimal("10000")
                drift = self.drift_bps / Decimal("10000")
                mr_k = self.mean_revert_bps / Decimal("10000")

                # Gaussian noise as Decimal (sample in float, then cast safely)
                noise_f = random.gauss(0.0, float(vol))
                z = Decimal(str(noise_f))

                # Mean reversion term (all Decimal)
                denom = self.mid if self.mid != 0 else Decimal("1")
                mr = ((self.mean_target - self.mid) / denom) * mr_k

                move = Decimal("1") + drift + z + mr
                self.mid *= move

                if self.mid <= 0:
                    self.mid = self.mean_target if self.mean_target > 0 else Decimal("1")

                # Update state
                if hasattr(self.state, "update_mid") and callable(getattr(self.state, "update_mid")):
                    self.state.update_mid(self.pair, self.mid)
                else:
                    self.state.mids[self.pair] = self.mid
                self.state.last_mid = float(self.mid)

                self.logger.info(f"[{self.pair}] mid={self.mid:.4f}")
            except Exception as e:
                self.logger.exception(f"[feeder] tick error: {e}")
            await asyncio.sleep(self.interval_ms / 1000.0)
