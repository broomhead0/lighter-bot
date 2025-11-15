"""
Inventory Adjustments Feature Module

Extracted from maker_engine.py to allow independent enable/disable.
Provides inventory-based spread widening and size reduction.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional

LOG = logging.getLogger("inventory")


class InventoryAdjustments:
    """
    Adjusts spreads and sizes based on inventory levels.
    
    Current implementation uses tiered thresholds.
    Can be simplified to binary (above/below threshold) in future.
    """
    
    def __init__(self, config: Dict[str, Any], state: Any = None):
        """
        Initialize inventory adjustments.
        
        Args:
            config: Inventory adjustment config (can be empty for defaults)
            state: StateStore instance (for inventory access)
        """
        self.config = config
        self.state = state
        self.enabled = config.get("enabled", False)
        
        if not self.enabled:
            return
        
        # Tiered thresholds for spread widening
        # Can be simplified to binary later
        self.threshold_low = Decimal(str(config.get("threshold_low", "0.01")))  # 0.01 SOL
        self.threshold_med = Decimal(str(config.get("threshold_med", "0.02")))  # 0.02 SOL
        self.threshold_high = Decimal(str(config.get("threshold_high", "0.03")))  # 0.03 SOL
        
        # Spread adjustments (bps)
        self.spread_bps_low = float(config.get("spread_bps_low", 2.0))
        self.spread_bps_med = float(config.get("spread_bps_med", 4.0))
        self.spread_bps_high = float(config.get("spread_bps_high", 6.0))
        
        # Size multipliers
        self.size_mult_low = float(config.get("size_mult_low", 0.75))
        self.size_mult_med = float(config.get("size_mult_med", 0.50))
        self.size_mult_high = float(config.get("size_mult_high", 0.50))
        
        self.market = "market:2"  # Will be set by maker_engine
        
        LOG.info(
            "[inventory] initialized: enabled=%s, thresholds=[%.3f, %.3f, %.3f]",
            self.enabled,
            float(self.threshold_low),
            float(self.threshold_med),
            float(self.threshold_high),
        )
    
    def set_market(self, market: str):
        """Set market identifier for inventory lookups."""
        self.market = market
    
    def get_spread_adjustment_bps(self, inventory: Optional[Decimal] = None) -> float:
        """
        Get spread adjustment in basis points based on inventory.
        
        Args:
            inventory: Current inventory (if None, fetches from state)
        
        Returns:
            Additional spread in basis points
        """
        if not self.enabled:
            return 0.0
        
        if inventory is None:
            inventory = self._get_inventory()
        
        inventory_abs = abs(inventory)
        
        # Tiered thresholds
        if inventory_abs > self.threshold_high:
            return self.spread_bps_high
        elif inventory_abs > self.threshold_med:
            return self.spread_bps_med
        elif inventory_abs > self.threshold_low:
            return self.spread_bps_low
        
        return 0.0
    
    def get_size_multiplier(self, inventory: Optional[Decimal] = None) -> float:
        """
        Get size multiplier based on inventory.
        
        Args:
            inventory: Current inventory (if None, fetches from state)
        
        Returns:
            Size multiplier (1.0 = no change, < 1.0 = reduce size)
        """
        if not self.enabled:
            return 1.0
        
        if inventory is None:
            inventory = self._get_inventory()
        
        inventory_abs = abs(inventory)
        
        # Tiered thresholds
        if inventory_abs > self.threshold_med:
            return self.size_mult_med
        elif inventory_abs > self.threshold_low:
            return self.size_mult_low
        
        return 1.0
    
    def _get_inventory(self) -> Decimal:
        """Get current inventory from state."""
        if not self.state or not hasattr(self.state, "get_inventory"):
            return Decimal("0")
        
        try:
            inv_raw = self.state.get_inventory(self.market)
            if inv_raw is not None:
                return Decimal(str(inv_raw))
        except Exception:
            pass
        
        return Decimal("0")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state for debugging."""
        inventory = self._get_inventory()
        return {
            "enabled": self.enabled,
            "inventory": str(inventory),
            "inventory_abs": str(abs(inventory)),
            "spread_adjustment_bps": self.get_spread_adjustment_bps(inventory),
            "size_multiplier": self.get_size_multiplier(inventory),
        }

