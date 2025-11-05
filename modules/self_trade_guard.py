import logging
from decimal import Decimal
from typing import Optional


class SelfTradeGuard:
    """
    Protects against crossed-book quoting, excessive inventory exposure, and invalid states.
    - Accepts either 'max_inventory' or 'max_inventory_notional' in cfg.
    - Works with dict-style state.inventory (per-pair) or scalar.
    - Uses per-market mid from state.mids[market] when available, else state.last_mid.
    """

    def __init__(self, state, cfg: dict):
        self.state = state
        self.logger = logging.getLogger("guard")
        self.cfg = cfg or {}

        # --- Price band protection ---
        self.price_band_bps = Decimal(
            str(self.cfg.get("price_band_bps", 50))
        )  # ±bps around mid
        self.crossed_book_protection = bool(
            self.cfg.get("crossed_book_protection", True)
        )

        # --- Inventory caps ---
        max_inv_units = self.cfg.get("max_position_units", 0.01)
        max_inv_notional = (
            self.cfg.get("max_inventory")
            or self.cfg.get("max_inventory_notional")
            or 1000  # safe default
        )
        try:
            self.max_position_units = Decimal(str(max_inv_units))
        except Exception:
            self.max_position_units = Decimal("0.01")

        try:
            self.max_inventory = Decimal(str(max_inv_notional))
        except Exception:
            self.max_inventory = Decimal("1000")

        # --- Kill-switch flags ---
        self.kill_on_crossed_book = bool(self.cfg.get("kill_on_crossed_book", True))
        self.kill_on_inventory_breach = bool(
            self.cfg.get("kill_on_inventory_breach", True)
        )
        self.backoff_seconds_on_block = int(self.cfg.get("backoff_seconds_on_block", 2))

    # ---------------------- Helpers ----------------------

    def _get_mid_for_market(
        self, market: Optional[str], fallback_mid: Decimal
    ) -> Decimal:
        # Try StateStore.get_mid() first
        if hasattr(self.state, "get_mid") and market:
            try:
                mid = self.state.get_mid(market)
                if mid is not None:
                    return Decimal(str(mid))
            except Exception:
                pass
        # Fallback: state.mids dict
        mids = getattr(self.state, "mids", None)
        if isinstance(mids, dict) and market in mids:
            try:
                return Decimal(str(mids[market]))
            except Exception:
                pass
        # Fallback: state.last_mid (float) or provided fallback
        last_mid = getattr(self.state, "last_mid", None)
        try:
            return Decimal(str(last_mid)) if last_mid is not None else fallback_mid
        except Exception:
            return fallback_mid

    def _get_inventory_for_market(self, market: Optional[str]) -> Decimal:
        # Try StateStore.get_inventory() first
        if hasattr(self.state, "get_inventory"):
            try:
                inv = self.state.get_inventory(market)
                if isinstance(inv, Decimal):
                    return inv
                if isinstance(inv, dict) and market:
                    return Decimal(str(inv.get(market, 0)))
                return Decimal(str(inv))
            except Exception:
                pass
        # Fallback: state.inventory dict or scalar
        inv = getattr(self.state, "inventory", 0)
        # dict per-pair inventory
        if isinstance(inv, dict):
            try:
                v = inv.get(market, 0) if market else 0
                return Decimal(str(v))
            except Exception:
                return Decimal("0")
        # scalar inventory
        try:
            return Decimal(str(inv))
        except Exception:
            return Decimal("0")

    # ---------------------- Core Checks ----------------------

    def _check_crossed_book(self, mid: Decimal, bid: Decimal, ask: Decimal) -> bool:
        if not self.crossed_book_protection:
            return True
        if bid >= ask:
            self.logger.warning(
                f"[guard] crossed book detected (bid {bid} >= ask {ask})"
            )
            if self.kill_on_crossed_book:
                self.logger.error("[guard] Kill-switch: crossed-book state")
            return False
        return True

    def _check_price_band(self, mid: Decimal, bid: Decimal, ask: Decimal) -> bool:
        band_frac = self.price_band_bps / Decimal(10000)
        lower_bound = mid * (Decimal(1) - band_frac)
        upper_bound = mid * (Decimal(1) + band_frac)
        if bid < lower_bound or ask > upper_bound:
            self.logger.info(
                f"[guard] quote outside price band ±{self.price_band_bps}bps: "
                f"bid={bid}, ask={ask}, mid={mid}"
            )
            return False
        return True

    def _check_inventory(self, market: Optional[str], ref_mid: Decimal) -> bool:
        inv = self._get_inventory_for_market(market)
        notional = abs(inv) * ref_mid
        if abs(inv) > self.max_position_units or notional > self.max_inventory:
            self.logger.warning(
                f"[guard] Inventory breach mkt={market}: inv={inv}, notional={notional}, "
                f"limits=({self.max_position_units} units, {self.max_inventory} notional)"
            )
            if self.kill_on_inventory_breach:
                self.logger.error("[guard] Kill-switch: inventory exceeded")
            return False
        return True

    # ---------------------- Public API ----------------------

    def is_allowed(
        self, mid: Decimal, bid: Decimal, ask: Decimal, market: Optional[str] = None
    ) -> bool:
        """Return True if quoting is allowed for given market."""
        if not self._check_crossed_book(mid, bid, ask):
            return False
        if not self._check_price_band(mid, bid, ask):
            return False
        # Use a reference mid for notional (per-market if available)
        ref_mid = self._get_mid_for_market(market, mid)
        if not self._check_inventory(market, ref_mid):
            return False
        return True
