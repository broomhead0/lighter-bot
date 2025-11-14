# Profitability Analysis - November 13, 2025

## Problem Statement
Bot is unprofitable. Need to identify root causes and implement fixes based on actual performance data.

## Key Findings from Historical Data

### 1. Regime Performance (from regime analysis)
- **Up-trend (> +0.1%) windows**: Averaged **+$16** ✅ (favorable)
- **Down-trend (< -0.1%) windows**: Averaged **-$13** ❌ (problematic)
- **Low-vol (≤ 0.0006)**: Yielded **+$5.36** ✅ (small but positive)
- **Mid/high volatility**: Drove **negative PnL** ❌

### 2. Hedger Cost Analysis
- **Large crosses (≥0.08 SOL)**: Cost **~$16-18 each** and erode maker edge
- **Impact**: These expensive crosses happen during low liquidity periods
- **Correlation**: Overnight (low vol) has worse performance due to more large crosses

### 3. Inventory Correlation
- **Realized PnL vs base delta**: ≈ **-1.0 correlation**
- **Meaning**: Exposure direction drives bleed - any inventory buildup costs money
- **Root cause**: Hedging costs exceed maker edge when inventory accumulates

### 4. Market Hours Performance
- **NY Market Hours (high vol)**: Better performance, fewer large crosses, more liquidity ✅
- **Overnight (low vol)**: Worse performance, more large crosses due to lower liquidity ❌

## Root Causes of Unprofitability

1. **Down-trend losses**: Bot loses $13 per downtrend window while only making $16 per uptrend
   - This means downtrends need to be much better handled
   - Current trend cooldown (45s) might not be enough

2. **Hedger costs too high**: Large crosses cost $16-18 each
   - Even with tightened parameters (0.06 SOL max clip, 0.02 SOL trigger)
   - Need to prevent large crosses entirely or reduce costs further

3. **Inventory buildup causes bleed**: Any inventory costs money to hedge
   - Need to keep inventory flatter (current target: 0.005 SOL)
   - Need to hedge earlier (current trigger: 0.02 SOL)

4. **Mid/high volatility losses**: Bot loses money in these regimes
   - Volatility-aware adjustments might not be enough
   - May need to pause or be more defensive during high vol

## Proposed Changes Based on Findings

### 1. More Aggressive Downtrend Handling
**Problem**: Down-trends lose $13/window vs $16/window in uptrends

**Current Config**:
- `down_threshold_bps: 6` - triggers when 45s return < -6 bps
- `down_cooldown_seconds: 45` - pauses bids for 45s
- `down_extra_spread_bps: 6.0` - adds 6 bps spread

**Proposed Changes**:
- Lower `down_threshold_bps: 4` - trigger earlier (softer downtrends)
- Increase `down_cooldown_seconds: 60` - pause longer during downtrends
- Increase `down_extra_spread_bps: 8.0` - wider spreads to avoid fills
- Make defensive regime more aggressive during downtrends

### 2. Further Reduce Hedger Costs
**Problem**: Large crosses cost $16-18 each, eroding edge

**Current Config**:
- `max_clip_units: 0.06` - max hedge size
- `trigger_units: 0.02` - hedge when inventory > 0.02 SOL
- `target_units: 0.005` - target inventory after hedge

**Proposed Changes**:
- Lower `max_clip_units: 0.04` - smaller max hedge (fewer large crosses)
- Lower `trigger_units: 0.015` - hedge earlier (prevent buildup)
- Lower `target_units: 0.003` - flatter target (less residual inventory)
- Increase `passive_wait_seconds: 0.5` - wait longer for passive fills (cheaper)

### 3. Better Volatility Response
**Problem**: Mid/high volatility drives negative PnL

**Current Config**:
- `low_vol_pause_threshold_bps: 4.5` - pause when vol < 4.5 bps
- `high_vol_threshold_bps: 9` - reduce size when vol > 9 bps
- `pause_threshold_bps: 30` - pause when vol > 30 bps

**Proposed Changes**:
- Consider pausing or being more defensive during mid-volatility (8-15 bps)
- Maybe add a "dangerous volatility" pause zone between 15-25 bps
- Reduce maker size more aggressively during high vol periods

### 4. More Aggressive Inventory Control
**Problem**: Any inventory buildup causes bleed (correlation = -1.0)

**Current Config**:
- `inventory_soft_cap: 0.10` - maker slows when inventory > 0.10 SOL
- Guard limits: `max_position_units: 0.3`, `max_inventory_notional: 50`

**Proposed Changes**:
- Lower `inventory_soft_cap: 0.05` - trigger earlier
- Make maker asymmetric: reduce bid size when long, reduce ask size when short
- Add inventory-based spread widening: wider spreads as inventory grows

## Metrics to Track for Validation

After implementing changes, monitor:
1. **FIFO realized PnL** - Should be positive or neutral
2. **Down-trend performance** - Should lose less or break even
3. **Hedger cross frequency** - Should see fewer large crosses (>0.05 SOL)
4. **Average inventory** - Should stay < 0.01 SOL most of the time
5. **Hedger costs** - Average cost per cross should decrease

## Implementation Priority

1. **Priority 1**: More aggressive downtrend handling (highest impact)
2. **Priority 2**: Further reduce hedger costs (direct cost reduction)
3. **Priority 3**: Better volatility response (reduce mid/high vol losses)
4. **Priority 4**: More aggressive inventory control (prevent buildup)

## Expected Impact

If these changes work:
- **Down-trend losses**: Should reduce from -$13 to near break-even
- **Hedger costs**: Should reduce by ~30-40% (fewer large crosses)
- **Overall PnL**: Should move from negative to neutral/slightly positive
- **Edge preservation**: Should keep more of maker edge by reducing hedging costs

## Next Steps

1. Implement Priority 1 & 2 changes
2. Deploy and monitor for 2-4 hours
3. Export PnL windows and compare to historical performance
4. Iterate based on results

