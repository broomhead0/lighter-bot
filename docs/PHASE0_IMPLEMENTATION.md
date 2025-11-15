# Phase 0 Implementation: Feature Extraction

**Status**: In Progress  
**Goal**: Extract complex features into modules without changing behavior

---

## Approach

Given the size of the codebase (maker_engine.py: ~1152 lines, hedger.py: ~700+ lines), we'll extract features incrementally:

1. Create feature module stubs with interfaces
2. Extract logic one feature at a time
3. Update maker_engine.py to use features (with fallback to old logic)
4. Test after each feature to ensure no behavior change
5. Once all extracted, simplify core

---

## Feature Modules to Create

1. ✅ `modules/features/__init__.py` - Created
2. ⏳ `modules/features/trend_filter.py` - Simple trend detection (priority #1)
3. ⏳ `modules/features/inventory_adjustments.py` - Binary inventory adjustments
4. ⏳ `modules/features/pnl_guard.py` - Simplified PnL guard
5. ⏳ `modules/features/volatility_adjustments.py` - EMA-based volatility (to be simplified later)
6. ⏳ `modules/features/regime_switcher.py` - Regime switching (to be removed later)
7. ⏳ `modules/features/hedger_passive_logic.py` - Hedger passive fills

---

## Progress

- [x] Created features directory and __init__.py
- [ ] Extract trend filter
- [ ] Extract inventory adjustments  
- [ ] Extract PnL guard
- [ ] Extract volatility adjustments
- [ ] Extract regime switcher
- [ ] Extract hedger passive logic
- [ ] Refactor maker_engine.py to use features
- [ ] Refactor hedger.py to use features
- [ ] Test: verify no behavior change

