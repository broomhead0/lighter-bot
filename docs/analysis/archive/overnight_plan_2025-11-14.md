# Overnight Plan - November 14, 2025

## Current Situation
- **UI PnL**: -$13 since 11/10
- **Root cause**: Inventory losses (-$22.27) eroding cash flow (+$9.27)
- **Recent fixes**:
  - ✅ Hedger notional check bug fixed (OR logic) - DEPLOYED
  - ✅ Asymmetric quoting - DEPLOYED
  - ✅ Notional fix for maker orders - DEPLOYED

## Overnight Strategy

### Option 1: Conservative - Widen Spreads Slightly (RECOMMENDED)
**Rationale**:
- Overnight typically has lower liquidity (from previous findings)
- Slightly wider spreads = more edge per fill, fewer fills
- Reduces risk of accumulating inventory overnight
- Small change, low risk

**Change**:
- `maker.spread_bps`: 12.0 → 13.0 bps
- **Impact**: ~8% wider spreads, slightly less volume, more edge per fill

### Option 2: Let It Run As-Is
**Rationale**:
- Fixes just deployed, should start helping
- Don't want to change too much at once
- Can evaluate in the morning

**Action**: No changes, just monitor

### Option 3: More Aggressive - Tighter Hedger
**Rationale**:
- Prevent any inventory buildup overnight
- Hedger already working, make it even more aggressive

**Change**:
- `hedger.trigger_units`: 0.010 → 0.008 (hedge earlier)
- `hedger.target_units`: 0.001 → 0.0005 (flatter target)

**Risk**: Might cause more hedging costs if too aggressive

## Recommendation: **Option 1 - Widen Spreads Slightly**

**Why**:
1. **Low risk**: Small change (12 → 13 bps), won't break anything
2. **Conservative**: Better for overnight with lower liquidity
3. **Aligns with findings**: Overnight had worse performance (more large crosses)
4. **More edge**: Slightly wider spreads help if maker fills happen
5. **Less inventory risk**: Fewer fills = less chance of inventory buildup

## What to Check in the Morning

### Primary Metrics
1. **UI PnL**: Check if it improved or continued bleeding
   - Target: Stopped bleeding or improved
   - Red flag: Lost more than ~$5 overnight

2. **Inventory levels**: Check logs for inventory patterns
   - Target: Mostly < 0.01 SOL
   - Red flag: Frequent builds > 0.02 SOL

3. **Hedger activity**: Check if hedger is executing
   - Target: Executes when inventory > 0.010
   - Red flag: Inventory builds but hedger doesn't execute

4. **PnL guard frequency**: Check how often it engaged
   - Target: Less frequent (if inventory stays flat)
   - Red flag: Still engaging every 15 seconds

### How to Check (Morning Commands)
```bash
# Check UI PnL (manual check)
# Check logs for inventory
railway logs --service lighter-bot --tail 2000 | grep "position updated" | tail -50

# Check hedger execution
railway logs --service lighter-bot --tail 2000 | grep "hedger.*executing" | tail -20

# Check PnL guard
railway logs --service lighter-bot --tail 2000 | grep "PnL guard" | tail -20
```

## Expected Overnight Performance

### Best Case
- Inventory stays flat (< 0.01 SOL)
- Hedger executes when needed
- PnL stabilizes or improves slightly
- UI PnL doesn't bleed further

### Realistic Case
- Inventory fluctuates but hedger flattens quickly
- Slight PnL improvement or neutral
- UI PnL maybe -$1 to -$2 additional overnight

### Worst Case
- Inventory still building up
- Hedger not keeping up
- PnL continues bleeding
- **Action needed**: More aggressive changes in morning

## Morning Decision Tree

```
Check UI PnL
├─ Improved or neutral → Continue monitoring, maybe optimize
├─ Slight bleed (-$1 to -$2) → Monitor more, check if trend improving
└─ Significant bleed (>-$3) → More aggressive changes needed
    ├─ Tighten hedger params
    ├─ Widen spreads further
    └─ Consider pausing during specific conditions
```

## Recommended Action: Widen Spreads to 13 bps

**Safe change**: +1 bps wider spreads (12 → 13)
**Impact**: More conservative, better edge, less inventory risk
**Risk**: Low - won't break anything, just slightly less volume

**After making change**:
- Let it run overnight
- Check in morning (use commands above)
- Evaluate if performance improved
- Decide next steps based on overnight results


