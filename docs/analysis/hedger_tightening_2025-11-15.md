# Hedger Tightening - November 15, 2025

## Problem

**Overnight observation**: Inventory still building to 0.075-0.077 SOL before hedger flattens it.

**Pattern observed**:
- Inventory builds to 0.075-0.077 SOL
- Hedger executes (0.030 SOL clips)
- Flattens to ~0.001-0.015
- Then builds again
- **Cycle repeats** → Multiple hedging costs

**Impact**: 
- Each hedge cycle costs ~$4-5 (0.030 SOL taker cross at ~$138)
- Frequent cycles erode maker edge
- Net result: -$0.25/hour loss rate

## Solution: Further Tighten Hedger

### Changes Made

```yaml
hedger:
  trigger_units: 0.010 → 0.008  # Hedge earlier (~$1.10 at $138)
  target_units: 0.001 → 0.0005  # Flatter target
  cooldown_seconds: 2.0 → 1.5    # Faster response
```

### Rationale

1. **Earlier trigger (0.008)**: 
   - Hedger activates when inventory = 0.008 SOL (~$1.10)
   - Prevents buildup to 0.075 SOL
   - Smaller clips = cheaper hedges

2. **Flatter target (0.0005)**:
   - Target inventory after hedge: 0.0005 SOL (~$0.07)
   - Nearly flat, less residual inventory
   - Reduces chance of quick rebuild

3. **Faster cooldown (1.5s)**:
   - Hedger can respond faster to new inventory
   - Less time for inventory to accumulate
   - More frequent but smaller hedges

## Historical Context

### Previous Tightening (from CHANGES_SUMMARY.md)

**trigger_units progression**:
- Started: 0.07
- → 0.05
- → 0.04
- → 0.02
- → 0.015
- → 0.010 (current)
- → 0.008 (new)

**target_units progression**:
- Started: 0.02
- → 0.015
- → 0.003
- → 0.001 (current)
- → 0.0005 (new)

**cooldown_seconds progression**:
- Started: 5.0
- → 3.0
- → 2.0 (current)
- → 1.5 (new)

### Why We Keep Tightening

**Finding**: Inventory buildup causes unrealized losses
- Previous analysis: -$22.27 unrealized losses eroding +$9.27 cash flow
- Root cause: Inventory accumulating and losing value
- Solution: Keep inventory flatter, hedge earlier

## Expected Impact

### Positive
- **Smaller inventory builds**: Max ~0.008 SOL before hedging (vs 0.075)
- **Cheaper hedges**: Smaller clips = lower taker costs
- **Faster response**: Less time for inventory to accumulate
- **Better coordination**: Hedger responds before inventory gets large

### Tradeoffs
- **More frequent hedging**: But smaller clips should offset cost
- **Potential over-hedging**: If too aggressive, might hedge unnecessarily
- **Need to monitor**: Ensure this doesn't cause excessive hedging costs

## Monitoring Plan

### Metrics to Track (Next 4-6 Hours)

1. **Inventory levels**:
   - Target: Mostly < 0.008 SOL (new trigger)
   - Red flag: Still building to > 0.05 SOL frequently

2. **Hedger execution frequency**:
   - Should increase (triggering earlier)
   - But clips should be smaller (cheaper)

3. **UI PnL trend**:
   - Target: Loss rate decreases or stabilizes
   - Red flag: Loss rate increases (over-hedging)

4. **Hedger costs**:
   - Average cost per hedge should decrease (smaller clips)
   - Total hedging costs should decrease despite more frequent hedging

### Success Criteria

✅ **Good signs**:
- Inventory stays < 0.01 SOL most of time
- Loss rate decreases or stays same
- Hedger costs per hedge decrease

⚠️ **Warning signs**:
- Inventory still building to > 0.05 SOL
- Loss rate increases (over-hedging)
- Hedger executing too frequently (every few seconds)

## Next Steps

1. **Monitor for 4-6 hours** after deploy
2. **Check inventory patterns** - should stay flatter
3. **Compare loss rate** - should improve or stay same
4. **If working well**: Continue monitoring
5. **If not working**: Consider even tighter params or different approach

## Comparison to Previous Tightening

**Similar to previous changes**: Yes, we've tightened hedger params multiple times
- Each time: Trigger lower, target flatter, cooldown faster
- **Pattern**: Progressive tightening as we learn inventory control is critical
- **This iteration**: Further refinement based on overnight observation

**Difference**: This is incremental tightening, not a major change
- Previous: 0.010 → 0.015 was a bigger jump
- This: 0.010 → 0.008 is smaller refinement
- **Rationale**: Fine-tuning based on specific observation (0.075 SOL builds)

