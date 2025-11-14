# Performance Check - November 14, 2025 @ 03:30 PT

## Current Market Conditions

### External SOL Volatility (Binance 1m)
- **Last 60 minutes**: 12.40 bps (NORMAL volatility regime)
- **Last 15 minutes**: 13.56 bps
- **Regime**: Normal trading conditions (between 6.0-30.0 bps threshold)

### Market Assessment
- ✅ **External volatility (12.40 bps) suggests normal trading conditions**
- ⚠️ **Above regime switch threshold (6.0 bps)** - Should be in aggressive regime
- ✅ **Below high-vol pause threshold (30.0 bps)** - Maker should be active

## Bot Performance Analysis

### PnL Summary (Last ~5 hours, 628 windows)
- **Total realized PnL**: Need to calculate from CSV
- **Average realized PnL per 5-min window**: Need to calculate
- **Windows analyzed**: 628 (5-minute windows)

### Observations from CSV:
Looking at recent PnL windows:
- Frequent large hedger crosses (~$10-10.6 per window when hedger volume > 0)
- Mix of small maker wins (~$1.5-4.2) and hedger costs (~$10)
- Inventory swings: base_delta varies between -0.075 and +0.075 SOL

### Patterns Identified:
1. **Large hedger crosses**: ~$10-10.6 per cross (consistent with previous findings)
2. **Small maker wins**: ~$1.5-4.2 per window when maker volume present
3. **Net result**: Maker wins are too small to offset hedger costs

## Comparison to Previous Findings

### From CHANGES_SUMMARY.md KEY LEARNINGS:
- **Down-trend (< -0.1%) windows**: Averaged **-$13** ❌
- **Up-trend (> +0.1%) windows**: Averaged **+$16** ✅
- **Low-vol (≤ 0.0006)**: Yielded **+$5.36** ✅
- **Mid/high volatility**: Drove **negative PnL** ❌

### Current Situation:
- **Current volatility**: 12.40 bps (MID-VOLATILITY regime)
- **Previous finding**: Mid/high volatility drove negative PnL
- **This aligns**: We're in mid-volatility and likely seeing negative PnL

## Recent Deploy Status

### Last Deploy: ~2 hours ago (01:36 PT)
- **Notional fix**: Orders now meet both size AND notional requirements ✅
- **Hedger notional check fix**: Changed from AND to OR logic ✅

### Current Issues:
1. **Hedger blocked**: Inventory stuck at 0.018 SOL, hedger detecting but not executing
   - **Root cause**: Notional check was using AND logic (fixed in latest deploy)
   - **Status**: Awaiting redeploy to verify fix

2. **PnL guard engaging frequently**: Every 15 seconds
   - **Indicates**: FIFO realized PnL below -$0.20 threshold
   - **Cause**: Inventory buildup + hedger not flattening

3. **Asymmetric quoting working**: ✅
   - Maker disabling bids when long inventory
   - Working WITH hedger instead of against it

## Expected After Hedger Fix Deploys

Once the hedger notional fix (OR logic) deploys:
1. **Hedger should execute** when inventory > 0.010 SOL (even if notional < $4.0)
2. **Inventory should flatten faster**
3. **PnL guard frequency should decrease**
4. **Better coordination** between maker and hedger

## Next Steps

1. **Wait for hedger fix to deploy** (OR logic for notional check)
2. **Monitor for 30-60 minutes** after deploy:
   - Check if hedger executes when inventory > 0.010 SOL
   - Verify inventory flattens below 0.010 SOL
   - Check PnL guard frequency (should decrease)
   - Monitor overall PnL trend

3. **Run full regime analysis** once we have:
   - Overlapping timestamp data (fix CSV timestamp conversion)
   - Recent candle data that matches PnL windows

4. **Compare performance** to previous findings:
   - Are we still losing in mid-volatility? (12.40 bps suggests yes)
   - Are down-trend losses still -$13/window?
   - Has asymmetric quoting improved inventory control?

## Recommendations

### Immediate (After Hedger Fix Deploys):
- Monitor hedger execution and inventory flattening
- Check if PnL improves with better hedger coordination

### Short-term (Next 24 hours):
- Run full regime analysis with corrected timestamps
- Compare to historical performance patterns
- Validate if Phase 2 changes (asymmetric quoting) are helping

### If Still Losing Money:
- Consider pausing maker during mid-volatility (8-15 bps) if losses persist
- Review if hedger costs are still too high even with smaller clips
- Consider widening base spread further (currently 12 bps)

## Key Metrics to Track

1. **FIFO realized PnL** (target: neutral or positive)
2. **Average inventory** (target: < 0.01 SOL most of time)
3. **PnL guard activation frequency** (should decrease with better inventory control)
4. **Hedger cross frequency and average cost** (target: fewer large crosses)
5. **Maker volume vs hedger volume ratio** (maker should generate more edge than hedger costs)

