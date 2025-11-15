"""
Feature modules for incremental enable/disable testing.

Each feature is optional and can be enabled via config.
Features are extracted from main modules to allow independent testing.
"""

from typing import Optional

# Feature classes will be imported here as they're created
__all__ = [
    'VolatilityAdjustments',
    'TrendFilter',
    'RegimeSwitcher',
    'PnLGuard',
    'InventoryAdjustments',
    'HedgerPassiveLogic',
]

