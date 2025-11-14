# Morning Checklist - November 15, 2025

## Quick Status Check

### 1. Check UI PnL (Primary Metric)
**Question**: How much did we lose overnight?
- **Target**: Stopped bleeding or only -$1 to -$2 additional
- **Red flag**: Lost > $3 overnight

**Action**: 
- Check UI for total PnL
- Compare to -$13 baseline from yesterday
- Note overnight change

### 2. Check Recent Logs
```bash
# Inventory levels (last 100 updates)
railway logs --service lighter-bot --tail 5000 | grep "position updated" | tail -100

# Hedger execution (last 50 hedges)
railway logs --service lighter-bot --tail 5000 | grep "hedger.*executing" | tail -50

# PnL guard activity
railway logs --service lighter-bot --tail 5000 | grep "PnL guard" | tail -30

# Asymmetric quoting activity
railway logs --service lighter-bot --tail 5000 | grep "asymmetric" | tail -20
```

### 3. Quick Performance Summary
```bash
# Get recent metrics snapshot
railway ssh --service lighter-bot -- "curl -s http://localhost:9100/metrics 2>/dev/null | grep -E '(maker_fifo_realized|maker_regime_state|maker_volatility|hedger.*volume|inventory)'" | head -20
```

## Decision Matrix

### If PnL Improved or Neutral
✅ **Good**: Fixes are working
- Continue monitoring
- Maybe optimize parameters slightly
- Consider if we can reduce spreads back to 12 bps if working well

### If PnL Slight Bleed (-$1 to -$2)
⚠️ **Monitor**: Need more time
- Check if trend is improving (was worse, getting better?)
- Monitor for another 4-6 hours
- Check inventory levels - are they staying flatter?

### If PnL Significant Bleed (>-$3)
🔴 **Action Needed**: More aggressive changes
- Tighten hedger params (trigger 0.010 → 0.008, target 0.001 → 0.0005)
- Widen spreads further (13 → 14-15 bps)
- Check if hedger is actually executing
- Consider if maker is still adding to inventory

## Key Questions to Answer

1. **Is hedger executing when inventory > 0.010?**
   - Look for "hedger.*executing" logs
   - If not, hedger fix didn't deploy or there's another issue

2. **Is inventory staying flat?**
   - Most position updates should be < 0.01 SOL
   - If frequently > 0.02 SOL, hedger isn't keeping up

3. **Is asymmetric quoting working?**
   - Look for "asymmetric quoting: disabling" logs
   - Should see this when inventory exists

4. **Is PnL guard still engaging frequently?**
   - Should decrease if inventory stays flat
   - If still every 15 seconds, FIFO PnL still below threshold

## Next Steps Based on Results

### Scenario A: Working Well
- Continue current config
- Monitor for 24 hours
- Consider next optimizations

### Scenario B: Needs Adjustment
- Make targeted changes based on what's not working
- Monitor impact
- Iterate

### Scenario C: Still Losing
- More aggressive changes
- Consider pausing maker during specific conditions
- Run full regime analysis with new data

## Files to Review

1. `docs/analysis/overnight_plan_2025-11-14.md` - Overnight plan
2. `docs/analysis/pnl_discrepancy_2025-11-14.md` - PnL analysis
3. `docs/analysis/next_actions_2025-11-14.md` - Previous recommendations
4. `CHANGES_SUMMARY.md` - Key learnings

## Quick Commands Summary

```bash
# Get overview
railway logs --service lighter-bot --tail 1000 | grep -E "(inventory|hedger.*executing|PnL guard|asymmetric)" | tail -50

# Check deployment time
railway logs --service lighter-bot --tail 5000 | grep -E "(MakerEngine started|Initialized|Started)" | tail -3

# Get current state
railway ssh --service lighter-bot -- "curl -s http://localhost:9100/metrics 2>/dev/null | grep -E '(maker_|hedger_|metrics_)(fifo_realized|inventory|regime_state)'" | head -15
```

