# Phase 2 Decision Analysis - November 14, 2025

## Current Systems Overview

### ✅ **Systems We've Built:**
1. **PnL Guard** - Uses FIFO realized PnL, triggers at -$0.20, widens spreads +6bps, reduces size x0.85
2. **Dynamic Regime Switching** - Aggressive/defensive based on volatility (6.0 bps threshold)
3. **Trend Filter** - Downtrend cooldown (60s), spread widening (8bps), bid pause
4. **Volatility-Aware Spreads** - 7-13 bps range, size multipliers 0.7-1.1
5. **Hedger** - Trigger 0.010 SOL, target 0.001 SOL, max clip 0.03 SOL, cooldown 2.0s
6. **Inventory Soft Cap** - 0.05 SOL threshold for size reduction

### 📊 **Evaluation Metrics:**
- `maker_fifo_realized_quote` - FIFO realized PnL
- `maker_regime_state` - 0=defensive, 1=aggressive
- `maker_volatility_bps` - Current volatility
- `maker_trend_down_guard` - Trend filter state
- `maker_pnl_guard_active` - PnL guard state
- Inventory metrics, hedger volume/costs

## Log Analysis (Last 500 lines)

### Observations:
1. **Inventory Stuck**: 0.027 SOL persists for ~15+ checks (15+ seconds) despite hedger active
2. **Inventory Building**: Reaches 0.045 SOL before hedger can flatten
3. **PnL Guard Engaging Frequently**: Multiple triggers in short time (guard → clear → guard again)
4. **Maker Still Quoting Both Sides**: No asymmetric behavior when inventory exists
5. **Hedger Trying**: Detects inventory > trigger, but can't flatten fast enough

### The Core Problem:
**Maker continues quoting BOTH sides even when inventory exists, adding to position while hedger tries to flatten.**

Example:
- Inventory: 0.027 SOL (long)
- Maker: Still placing bids AND asks
- Result: More fills on bids → inventory grows → hedger can't keep up

## Systems Analysis

### What's Working:
✅ **PnL Guard**: Engaging correctly when losses occur, widening spreads appropriately
✅ **Regime Switching**: Should be switching based on volatility
✅ **Trend Filter**: Should pause bids during downtrends
✅ **Hedger**: Active, detecting inventory, trying to flatten

### What's NOT Working:
❌ **Inventory Control**: Maker doesn't reduce/stop quoting the "wrong" side when inventory exists
❌ **Asymmetric Quoting**: No logic to quote only asks when long, only bids when short
❌ **Inventory-Responsive Spreads**: Spreads don't widen based on inventory level

### What's Missing:
🔴 **Asymmetric Quoting** - The #1 missing piece:
- When long inventory: Stop/reduce bids, keep asking (work WITH hedger)
- When short inventory: Stop/reduce asks, keep bidding (work WITH hedger)
- Currently: Maker works AGAINST hedger by adding to position

## Why Phase 1 Changes Won't Be Enough

Phase 1 improvements (tighter hedger, more aggressive PnL guard) are good, BUT:

1. **Reactive, not preventive**: PnL guard triggers AFTER losses occur
2. **Hedger can't keep up**: Even with tighter params, maker is adding to inventory faster than hedger can flatten
3. **No inventory-based maker adjustment**: Maker doesn't reduce quoting when inventory exists
4. **Fundamental conflict**: Maker and hedger working against each other

## Recommendation: **YES, Implement Phase 2 Now**

### Why:
1. **Phase 1 is deployed**: New hedger params (0.010 trigger, 0.001 target, 0.03 max clip, 2.0s cooldown) are live
2. **Core problem is clear**: Inventory buildup from maker quoting both sides
3. **Asymmetric quoting is critical**: This is the missing piece that will make maker work WITH hedger
4. **High impact, low risk**: Code change is straightforward, addresses root cause
5. **Can validate quickly**: Should see immediate improvement in inventory control

### Phase 2 Implementation (Priority Order):

#### 1. **Asymmetric Quoting** (CRITICAL - Do First)
```python
# In maker_engine.py, before placing quotes:
inventory = self.state.get_inventory(self.market) or Decimal("0")
inventory_abs = abs(inventory)

# If inventory exceeds threshold, make quoting asymmetric
if inventory_abs > Decimal("0.01"):  # 0.01 SOL threshold
    if inventory > 0:  # Long inventory
        place_bid = False  # Don't add to long position
        place_ask = True   # Keep asking to flatten
    else:  # Short inventory
        place_bid = True   # Keep bidding to flatten
        place_ask = False  # Don't add to short position
```

#### 2. **Inventory-Based Spread Widening** (HIGH - Do Second)
```python
# Add spread bonus based on inventory:
inventory_bps_bonus = 0.0
if inventory_abs > Decimal("0.03"):
    inventory_bps_bonus = 6.0
elif inventory_abs > Decimal("0.02"):
    inventory_bps_bonus = 4.0
elif inventory_abs > Decimal("0.01"):
    inventory_bps_bonus = 2.0
```

#### 3. **Inventory-Based Size Reduction** (MEDIUM - Do Third)
```python
# Reduce size when inventory exists:
size_multiplier = 1.0
if inventory_abs > Decimal("0.02"):
    size_multiplier = 0.50
elif inventory_abs > Decimal("0.01"):
    size_multiplier = 0.75
```

### Expected Impact:
- **Inventory Control**: Should stay < 0.01 SOL most of the time
- **Maker/Hedger Coordination**: Maker will work WITH hedger instead of against it
- **PnL Guard Frequency**: Should engage less often (preventive vs reactive)
- **Overall PnL**: Should improve significantly

### Validation Plan:
1. Deploy Phase 2 changes
2. Monitor for 1-2 hours:
   - Inventory should stay flatter (< 0.01 SOL)
   - Maker should quote asymmetrically when inventory exists
   - PnL guard should engage less frequently
   - FIFO realized PnL should trend toward neutral/positive

## Decision: **Proceed with Phase 2 Implementation**

**Rationale:**
- Phase 1 improvements are good but insufficient
- Core problem (maker working against hedger) requires Phase 2
- Asymmetric quoting is the critical missing piece
- Can validate quickly, high impact, addresses root cause

**Next Steps:**
1. Implement asymmetric quoting logic
2. Add inventory-based spread widening
3. Add inventory-based size reduction
4. Deploy and monitor
5. Validate with 1-2 hours of data

