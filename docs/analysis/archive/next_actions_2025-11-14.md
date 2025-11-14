# Next Actions - November 14, 2025

## Current Situation

### Performance Reality Check
- **UI PnL**: -$13 since 11/10 (actual loss)
- **Cash flow**: +$9.27 (misleading - doesn't include unrealized)
- **Unrealized losses**: -$22.27 (inventory losing value)
- **Root cause**: Inventory accumulating and losing value faster than maker fills generate cash

### Recent Fixes
1. ✅ **Notional check bug fixed** (OR logic) - Hedger should execute when inventory > 0.010 SOL
2. ✅ **Asymmetric quoting deployed** - Maker stops quoting side that adds to position
3. ⏳ **Waiting for hedger fix to deploy** - Should flatten inventory faster

### Key Issues
- **Inventory buildup**: 0.001-0.073 SOL (fluctuating, not staying flat)
- **Unrealized losses**: Eating into cash flow gains
- **PnL guard engaging frequently**: Indicating FIFO PnL below -$0.20 threshold
- **Hedger activity**: Need to verify if notional fix has deployed

## Recommended Next Steps (Priority Order)

### 1. **Wait for Hedger Fix to Deploy** (30-60 minutes)
**Why**: The notional check bug was blocking hedger even when inventory exceeded trigger. This is the #1 issue.

**What to check**:
- Verify hedger is executing when inventory > 0.010 SOL
- Check if inventory flattens faster
- Monitor if PnL guard frequency decreases

**Expected impact**:
- Hedger should execute more frequently
- Inventory should stay flatter (< 0.01 SOL more consistently)
- Should reduce unrealized losses

### 2. **Monitor Performance for 2-4 Hours After Deploy**
**Why**: Need to see if fixes are working before making more changes.

**What to track**:
- Inventory levels (target: < 0.01 SOL most of the time)
- PnL guard frequency (should decrease if inventory stays flat)
- FIFO realized PnL from telemetry (true maker edge)
- Overall UI PnL trend (should stop bleeding or improve)

### 3. **If Still Losing Money After Monitoring**
**Consider**:

**Option A: Widen Spreads Further**
- Current: 12 bps base spread
- Proposed: 14-15 bps base spread
- **Rationale**: More edge per fill, fewer fills (but also less volume)
- **Tradeoff**: Less trading volume vs more edge per trade

**Option B: More Aggressive Inventory Control**
- Lower `inventory_soft_cap`: 0.05 → 0.03
- Tighter hedger params: trigger 0.010 → 0.008, target 0.001 → 0.0005
- **Rationale**: Keep inventory even flatter to prevent unrealized losses

**Option C: Pause Maker During Specific Conditions**
- If volatility between 8-15 bps (mid-volatility) continues to lose money
- Consider pausing maker during these regimes
- **Rationale**: Previous findings showed mid/high volatility drove negative PnL

**Option D: Run Full Regime Analysis**
- Export PnL windows with FIFO realized PnL (not just cash flow)
- Correlate with SOL price movements
- Identify which regimes are actually profitable vs losing money
- **Rationale**: Data-driven decisions on when to trade vs pause

### 4. **If Fixes Are Working**
**Consider**:
- Gradually increase maker size (if inventory stays flat)
- Optimize spreads based on volatility (already doing this)
- Enable premium fees once PnL is consistently neutral/positive

## Decision Tree

```
Is hedger fix deployed?
├─ NO → Wait 30-60 min, check logs for hedger execution
└─ YES → Monitor for 2-4 hours
    ├─ Inventory staying flat (< 0.01 SOL)?
    │   ├─ YES → Continue monitoring, check PnL trend
    │   └─ NO → Check why hedger isn't flattening (logs, config)
    │
    └─ PnL improving?
        ├─ YES → Continue monitoring, validate sustainability
        └─ NO → Consider Options A-D above
```

## Immediate Actions (Now)

1. **Check if hedger fix has deployed**
   - Look for hedger execution logs
   - Check if notional check is using OR logic (logs should show "check passed: notional=... OR inv=...")

2. **Check current inventory**
   - Should be < 0.01 SOL if hedger is working
   - If > 0.01 SOL, hedger should be executing

3. **Check PnL guard frequency**
   - Should decrease if inventory stays flat
   - If still engaging frequently, FIFO PnL still below threshold

## Metrics to Track

1. **Inventory levels** (target: < 0.01 SOL most of time)
2. **Hedger execution frequency** (should execute when inventory > 0.010 SOL)
3. **PnL guard frequency** (should decrease with better inventory control)
4. **UI PnL trend** (should stop bleeding or improve)
5. **FIFO realized PnL** (true maker edge - from telemetry)

## Expected Timeline

- **0-60 min**: Wait for hedger fix to deploy, verify it's working
- **1-4 hours**: Monitor performance with fixes active
- **4-24 hours**: Evaluate if additional changes needed
- **24+ hours**: Run full regime analysis with corrected data

## Key Insight

**The bot's maker strategy is generating cash flow (+$9.27), but inventory losses (-$22.27) are eroding it. The solution is to prevent inventory buildup, not necessarily to make more money from maker fills.**

This means:
- **Hedger is critical** - Must flatten inventory quickly
- **Asymmetric quoting helps** - Prevents adding to positions
- **Keeping inventory flat** is more important than maximizing maker volume

## Recommendation

**Wait and monitor**. The hedger fix should help significantly. If inventory stays flat, unrealized losses should decrease, and we should see improvement in overall PnL.

Only make more aggressive changes if, after 2-4 hours of monitoring, we're still seeing:
- Inventory > 0.01 SOL frequently
- PnL continuing to bleed
- PnL guard engaging very frequently


