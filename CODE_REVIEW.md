# Code Review: Simplification & Improvements

## 🎯 Goal Reminder
**Maximize points per dollar per day with ~$1k capital** by:
- Post-only maker quotes on 2-3 markets
- Occasional taker fills for organic activity
- Shift exposure to higher point-yield pairs

## ❌ Critical Issues (Must Fix)

### 1. **SelfTradeGuard NOT WIRED** ⚠️ CRITICAL
**Problem:** `SelfTradeGuard` exists but is **never called** by `MakerEngine`. This is a safety feature that should prevent crossed books and inventory breaches.

**Impact:** No protection against invalid quotes - could lead to losses or compliance issues.

**Fix:**
```python
# In MakerEngine._post_quotes() or before:
if self.guard:
    from decimal import Decimal
    if not self.guard.is_allowed(
        Decimal(str(mid)),
        Decimal(str(bid)),
        Decimal(str(ask)),
        self.market
    ):
        LOG.warning("[maker] quote blocked by guard")
        return  # Don't post invalid quote
```

### 2. **Maker Engine is DRY-RUN ONLY** ⚠️ CRITICAL
**Problem:** `MakerEngine._post_quotes()` is a no-op. The bot **cannot actually place orders**.

**Impact:** Bot doesn't do anything - just logs fake quotes. Can't make money.

**Fix:** Implement actual REST order placement:
- Use `core/rest_client.py` (already exists)
- Place post-only limit orders
- Track open orders
- Cancel/replace on refresh

### 3. **Cancel Discipline Not Enforced**
**Problem:** `maker.limits.max_cancels` is checked but not enforced - just logs warnings.

**Impact:** Could exceed exchange limits, get rate-limited or banned.

**Fix:** Actually throttle maker when limit exceeded:
```python
# Track cancel count, stop posting if exceeded
if self._cancel_count_this_minute >= self.max_cancels:
    LOG.warning("[maker] cancel limit exceeded, throttling")
    await asyncio.sleep(60)  # Wait a minute
```

## 🔧 Simplifications (Can Remove/Simplify)

### 4. **Remove Unused Code**
- **`modules/hedger.py`** - `HedgerDryRun` is never imported/used in main.py
- **`modules/_message_router.zombie`** - Dead file, should be deleted
- **`modules/ws_client.py`** - Redundant with `market_data_listener.py`
- **`modules/pair_selector.py`** - Referenced but likely unused (check if PairSelector is actually used)

### 5. **Simplify Adapter Pattern**
**Problem:** `_DSAdapter`, `_StateAdapter`, `_MakerUpdater` add unnecessary complexity.

**Current:** Complex try/except chains with fallbacks
**Better:** Direct usage, or simple wrapper if needed

**Why:** Over-engineering for optional dependencies. The optimizer should work with StateStore directly.

### 6. **Simplify Config Loading**
**Problem:** `core/config.py` defines dataclasses but `main.py` loads YAML directly with `yaml.safe_load()`.

**Options:**
- Remove `core/config.py` (unused)
- OR use it consistently everywhere

**Recommendation:** Keep YAML loading (simpler), remove unused `core/config.py`.

### 7. **Simplify Constructor Pattern**
**Problem:** `_try_construct()` with 6+ variants for each component is overkill.

**Current:**
```python
maker = _try_construct(MakerEngine, [
    ((), {"config": cfg, "state": state, ...}),
    ((), {"config": cfg, "state": state}),
    ((cfg, state), {}),
    ((state, cfg), {}),
    ((state,), {}),
    ((), {}),
])
```

**Better:** Standardize on one signature, or use dependency injection properly.

### 8. **Remove Redundant WS Code**
**Problem:** Both `ws_client.py` and `market_data_listener.py` handle WebSocket connections.

**Keep:** `market_data_listener.py` (more complete, has capture, synthetic fallback)
**Remove:** `ws_client.py` (unused?)

### 9. **Simplify StateStore**
**Problem:** Uses float for prices, but router uses Decimal. Inconsistent.

**Better:** Use Decimal throughout (already doing in router, should be consistent).

**Current:** `_mids: Dict[str, float]`
**Better:** `_mids: Dict[str, Decimal]`

## 📊 What's Actually Good (Keep)

✅ **Modular design** - Good separation of concerns
✅ **Replay system** - Useful for testing
✅ **Chaos injector** - Good for resilience testing (M8)
✅ **Telemetry** - Good for monitoring
✅ **Config-driven** - Easy to tweak
✅ **Decimal in router** - Correct precision handling

## 🎯 Recommendations by Priority

### **Priority 1: Fix Critical Functionality**
1. **Wire SelfTradeGuard into MakerEngine** - Safety critical
2. **Implement actual order placement** - Bot doesn't work without this
3. **Enforce cancel discipline** - Prevent rate limiting

### **Priority 2: Simplify Architecture**
4. Remove unused modules (hedger, zombie files)
5. Simplify adapter pattern
6. Remove redundant WS client
7. Standardize on one config system

### **Priority 3: Code Quality**
8. Use Decimal consistently throughout
9. Simplify constructor patterns
10. Clean up try/except chains

## 💡 Simplified Architecture Proposal

**Core Flow:**
```
WS → MessageRouter → StateStore (mids)
                    ↓
              MakerEngine (quotes) → SelfTradeGuard (validate) → REST (place orders)
                    ↓
              FundingOptimizer (select pairs)
```

**What to Remove:**
- HedgerDryRun (unused)
- ws_client.py (redundant)
- _message_router.zombie (dead code)
- Complex adapter layers
- _try_construct pattern (use standard constructors)

**What to Add:**
- Actual REST order placement
- SelfTradeGuard integration
- Cancel discipline enforcement
- Order tracking in StateStore

## 🔍 Missing Features for Production

1. **Order Management:**
   - Track open orders
   - Handle fills
   - Update inventory on fills
   - Cancel stale orders

2. **Fill Handling:**
   - Process fills from WS or REST
   - Update PNL
   - Update inventory
   - Trigger hedging if needed

3. **Kill-Switch Implementation:**
   - Actually stop maker on threshold breach
   - Not just log warnings

4. **Inventory Tracking:**
   - StateStore needs inventory tracking
   - Currently mentioned but not fully implemented

## 📝 Summary

**Good:** Architecture is sound, modular, testable. Replay/chaos are excellent additions.

**Bad:** Core functionality missing (order placement), safety features not wired, over-engineered in places.

**Recommendation:**
1. Fix critical issues first (order placement, guard wiring)
2. Remove unused code
3. Simplify adapter patterns
4. Then deploy

The bot is well-structured but needs the core trading logic implemented to actually work.

