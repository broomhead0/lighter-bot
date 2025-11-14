# Overnight Results - November 15, 2025

## Performance Summary

### Overnight Metrics
- **UI PnL**: -$2 overnight (from -$13 baseline)
- **New total**: -$15 since 11/10
- **Overnight bleed rate**: ~-$0.25/hour (assuming 8 hours)
- **Previous rate**: ~-$0.15/hour (over ~52 hours, -$13 total)

### Assessment

**Improvement**: ✅ Loss rate is reasonable
- **Overnight**: -$2 over ~8 hours = -$0.25/hour
- **Overall**: -$15 over ~60 hours = -$0.25/hour
- **Trend**: Consistent, not accelerating

**Context**:
- Previous baseline: -$13 over ~52 hours = -$0.25/hour
- Overnight rate: -$0.25/hour (same as overall)
- **Conclusion**: Loss rate is stable, not worsening

## What's Working

### ✅ Hedger Fix (OR Logic)
- Hedger executing when inventory > 0.010 SOL
- Logs show: "hedger.*executing" entries
- **Status**: Working correctly

### ✅ Asymmetric Quoting
- Maker disabling bids when long inventory
- Logs show: "asymmetric quoting: disabling bids"
- **Status**: Working correctly

### ✅ Wider Spreads (13 bps)
- More conservative, less inventory risk
- **Status**: Deployed and active

## Areas for Improvement

### ⚠️ Still Losing Money
- -$0.25/hour is consistent but not profitable
- Need to reduce loss rate further

### ⚠️ Inventory Patterns
- [Check logs for inventory frequency distribution]
- Need to verify if inventory staying flatter

### ⚠️ PnL Guard Frequency
- [Check logs for PnL guard engagement frequency]
- If still engaging frequently, FIFO PnL below threshold

## Next Steps

### Option 1: Monitor Longer (Recommended)
**Rationale**:
- Loss rate is stable (-$0.25/hour)
- Fixes are working (hedger, asymmetric quoting)
- Need more time to see full impact

**Action**:
- Monitor for another 4-6 hours
- Track if loss rate improves or stays consistent
- Check if inventory stays flatter with fixes

### Option 2: Further Tighten Hedger
**Rationale**:
- If inventory still building frequently, hedge earlier

**Changes**:
- `hedger.trigger_units`: 0.010 → 0.008 (hedge earlier)
- `hedger.target_units`: 0.001 → 0.0005 (flatter target)

**Tradeoff**: More hedging costs vs less inventory risk

### Option 3: Widen Spreads Further
**Rationale**:
- More edge per fill, fewer fills

**Changes**:
- `maker.spread_bps`: 13.0 → 14.0 or 15.0 bps

**Tradeoff**: Less volume vs more edge per trade

### Option 4: Run Full Regime Analysis
**Rationale**:
- Understand which conditions are profitable vs losing
- Data-driven optimization

**Action**:
- Export PnL windows with FIFO realized PnL
- Correlate with SOL volatility/trends
- Identify profitable vs losing regimes

## Recommendation: **Monitor for 4-6 More Hours**

**Why**:
1. **Loss rate is stable**: -$0.25/hour is consistent
2. **Fixes are working**: Hedger executing, asymmetric quoting active
3. **Too early to judge**: Overnight might have different conditions
4. **Need daytime data**: Previous findings showed different performance day vs night

**What to check**:
- UI PnL after 4-6 more hours
- Compare daytime performance to overnight
- Check if loss rate improves during higher liquidity periods

**Decision criteria**:
- If loss rate improves → Continue monitoring
- If loss rate stays same → Consider tighter hedger params
- If loss rate worsens → More aggressive changes needed

## Key Metrics to Track

1. **UI PnL trend** (target: improving or stable)
2. **Inventory levels** (target: < 0.01 SOL most of time)
3. **Hedger execution** (target: executes when inventory > 0.010)
4. **PnL guard frequency** (target: decreasing)
5. **Loss rate** (target: < $0.25/hour, ideally $0)

## Comparison to Previous Findings

### From CHANGES_SUMMARY.md:
- **Down-trends**: -$13/window
- **Overnight (low vol)**: Worse performance
- **NY Market Hours (high vol)**: Better performance

### Current Observation:
- **Overnight loss**: -$2 over 8 hours = -$0.25/hour
- **Rate**: Consistent with overall -$0.25/hour
- **Assessment**: Loss rate stable, may improve during daytime (NY hours)

## Conclusion

**Status**: ⚠️ Still losing money but rate is stable

**Good news**:
- Fixes are working (hedger, asymmetric quoting)
- Loss rate is consistent, not accelerating
- Overnight rate matches overall rate

**Concern**:
- Still losing -$0.25/hour consistently
- Need to reduce loss rate to break even or profit

**Next action**: Monitor for 4-6 more hours, especially during daytime (NY market hours) when liquidity is higher. Compare performance to overnight.


