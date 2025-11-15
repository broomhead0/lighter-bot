"""
Feature modules for incremental enable/disable testing.

Each feature is optional and can be enabled via config.
Features are extracted from main modules to allow independent testing.
"""

from typing import Optional

# Feature classes - import as created
try:
    from modules.features.trend_filter import TrendFilter
except ImportError:
    TrendFilter = None

try:
    from modules.features.inventory_adjustments import InventoryAdjustments
except ImportError:
    InventoryAdjustments = None

try:
    from modules.features.pnl_guard import PnLGuard
except ImportError:
    PnLGuard = None

__all__ = [
    'TrendFilter',
    'InventoryAdjustments',
    'PnLGuard',
    # 'VolatilityAdjustments',  # TODO
    # 'RegimeSwitcher',  # TODO
    # 'HedgerPassiveLogic',  # TODO
]

