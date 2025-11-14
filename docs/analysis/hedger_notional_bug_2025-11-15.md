# CRITICAL: Hedger Notional Bug - November 15, 2025

## Problem Discovery

**User reported**: -$2 overnight (from -$13 baseline) = -$15 total
**Investigation revealed**: Inventory stuck at 0.093 SOL despite constant hedging

### Root Cause

**Hedger clips were below exchange minimum notional!**

- **Hedger executing**: Every 1.5s, trying to hedge 0.0105 SOL
- **Clip size**: 0.0105 SOL (from PnL guard dampening: 0.03 * 0.35 = 0.0105)
- **Price**: ~$143
- **Notional**: 0.0105 * $143 = **$1.50**
- **Exchange minimum**: **$10.5**
- **Result**: Orders rejected (code 21706) but failing silently!

### Why This Happened

1. **PnL guard dampening**: When PnL guard active, reduces clip size:
   - `max_clip_units` (0.03) * `guard_clip_multiplier` (0.35) = 0.0105 SOL

2. **No notional check in hedger**: Maker has notional quantization, hedger didn't

3. **Orders failing silently**: Hedger thought it was executing, but orders were rejected

4. **Inventory stuck**: Maker adding inventory, hedger unable to flatten (orders failing)

### Impact

- **Inventory**: Stuck at 0.093 SOL (way above 0.008 trigger)
- **Hedger**: Executing constantly but ineffective
- **PnL**: Continuing to bleed (inventory losses)
- **Status**: Hedger completely broken!

## Fix

### Changes Made

1. **Added exchange minimums to hedger**:
   - `exchange_min_size`: 0.061 SOL (from maker config)
   - `exchange_min_notional`: 10.5 (from maker config)
   - `size_scale`: 1000 (from maker config)

2. **Added quantization logic** (similar to maker):
   - Ensure clip size meets minimum size (0.061 SOL)
   - Ensure clip size meets minimum notional (at current price)
   - Round up to nearest lot step to meet notional

3. **Added caps**:
   - Cap at `max_clip_units` (0.03 SOL)
   - Cap at current inventory (can't hedge more than we have)

### Code Logic

```python
# After PnL guard adjustment:
hedge_units = min(hedge_units, guard_clip)  # Could be 0.0105 SOL

# Ensure minimum size
if hedge_units < exchange_min_size (0.061):
    hedge_units = 0.061

# Ensure minimum notional
if price * hedge_units < exchange_min_notional ($10.5):
    min_size_for_notional = $10.5 / price
    hedge_units = max(hedge_units, quantize_up(min_size_for_notional))

# At $143 price:
# min_size_for_notional = $10.5 / $143 = 0.073 SOL
# hedger will use 0.073 SOL (meets notional) instead of 0.0105 SOL
```

## Expected Impact After Fix

### Immediate
- **Hedger will actually execute**: Orders will meet notional requirement
- **Inventory should flatten**: Hedger can finally remove inventory
- **No more stuck inventory**: 0.093 SOL should decrease

### Short-term
- **Inventory stays flatter**: Should stay < 0.008 SOL more consistently
- **PnL guard frequency**: Should decrease as inventory stays flat
- **UI PnL**: Should stabilize or improve

## Historical Context

### Similar Issue in Maker (Fixed Earlier)
- **Problem**: Maker orders rejected (code 21706) due to insufficient notional
- **Fix**: Added notional quantization to maker
- **Result**: Maker orders now go through successfully

### Why Hedger Was Missed
- Hedger doesn't use same code path as maker
- Notional check was only added to maker, not hedger
- PnL guard dampening exposed the bug (smaller clips → below minimum)

## Monitoring Plan

### After Deploy (0-30 minutes)
1. **Check hedger execution**:
   - Look for successful order submissions (not just "executing hedge" logs)
   - Verify orders actually fill (check position updates)

2. **Check inventory**:
   - Should decrease from 0.093 SOL
   - Should stay < 0.008 SOL after flattening

3. **Check for order rejections**:
   - Should NOT see code 21706 errors anymore
   - If still seeing, quantization might need adjustment

### After 1-2 Hours
1. **Inventory patterns**: Should stay flatter
2. **PnL guard frequency**: Should decrease
3. **UI PnL trend**: Should stabilize or improve

## Critical Insight

**This bug explains why we've been losing money!**

- **Cash flow**: +$9.27 (maker fills working)
- **Inventory losses**: -$22.27 (inventory stuck, losing value)
- **Root cause**: Hedger unable to flatten inventory (orders failing)
- **Net result**: -$13 loss

**Once this fix deploys, hedger should actually work and inventory should flatten!**

## Next Steps

1. ✅ Fix deployed - waiting for redeploy
2. ⏳ Monitor hedger execution (should see successful orders)
3. ⏳ Monitor inventory (should decrease from 0.093)
4. ⏳ Check UI PnL (should stabilize or improve)

## Lessons Learned

1. **Always check notional requirements** for both maker AND hedger
2. **Guard dampening can expose bugs** - smaller sizes may fall below minimums
3. **Silent failures are dangerous** - need better error logging
4. **Test all paths** - maker fixed, but hedger had same issue


