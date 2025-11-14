# MASTER DOCUMENT - Lighter Bot Profitability Journey

**Last Updated**: November 15, 2025  
**Purpose**: Single source of truth for bot state, learnings, and iteration strategy  
**When Context is Lost**: Read this document first to get back up to speed

---

## 🎯 Current Goal

**Make the bot profitable** - Currently losing ~-$0.25/hour, need to reach break-even or positive.

---

## 📊 Current Performance Status

### PnL Overview
- **Total Loss Since 11/10**: -$15 (was -$13 baseline, -$2 overnight)
- **Loss Rate**: ~-$0.25/hour (stable, not accelerating)
- **UI PnL**: Primary metric - includes realized + unrealized
- **FIFO Realized PnL**: Still below -$0.20 threshold (PnL guard engaging frequently)

### Recent Activity (Last 2 Hours)
- **Inventory**: 90% flat (0 or 0.000), 10% small/medium builds
- **Large Builds**: 2% of updates (still seeing 0.075 SOL jumps)
- **Hedger**: Working correctly, orders submitting successfully
- **PnL Guard**: Engaging every ~15 seconds, clearing quickly

### What's Working ✅
1. **Hedger fix deployed**: Orders meeting notional requirements, submitting successfully
2. **Inventory control improving**: 90% flat rate
3. **Asymmetric quoting active**: Maker cooperating with hedger
4. **Config strategy fixed**: Single source of truth (config.yaml)

---

## 🔍 Key Learnings (What We've Discovered)

### 1. Regime Performance
- **Up-trends (> +0.1%)**: Averaged **+$16** ✅ (profitable)
- **Down-trends (< -0.1%)**: Averaged **-$13** ❌ (biggest problem)
- **Low volatility (≤ 0.0006)**: Averaged **+$5.36** ✅ (small but positive)
- **Mid/high volatility**: Negative PnL ❌

### 2. Market Hours Performance
- **NY Market Hours (high vol)**: Better performance, fewer large crosses, more liquidity ✅
- **Overnight (low vol)**: Worse performance, more large crosses, lower liquidity ❌

### 3. Inventory Correlation
- **Realized PnL vs inventory**: ≈ **-1.0 correlation** (inventory buildup = losses)
- **Root cause**: Inventory accumulating and losing value faster than maker fills generate cash
- **Impact**: Cash flow +$9.27, but unrealized losses -$22.27 = net -$13

### 4. Hedger Costs
- **Large crosses (≥0.08 SOL)**: Cost **~$16-18 each**, erode maker edge
- **Smaller crosses**: Cheaper, but more frequent with tighter params

---

## 🛠️ Current Configuration (Active Settings)

### Maker Engine
```yaml
spread_bps: 13.0  # Widened for conservatism
inventory_soft_cap: 0.05  # Triggers earlier inventory control
volatility:
  low_vol_pause_threshold_bps: 0.0  # Disabled (was causing unnecessary pauses)
trend:
  down_threshold_bps: 4  # Triggers earlier on softer downtrends
  down_extra_spread_bps: 8.0  # Wider spreads during downtrends
  down_cooldown_seconds: 60  # Longer pauses in downtrends
pnl_guard:
  realized_floor_quote: -0.20  # Triggers earlier
  trigger_consecutive: 1  # Triggers immediately
  widen_bps: 6.0
  max_extra_bps: 10.0
```

### Hedger
```yaml
trigger_units: 0.008  # Hedge earlier (~$1.10 at $138)
target_units: 0.0005  # Flatter target
max_clip_units: 0.03  # Smaller clips
cooldown_seconds: 1.5  # Faster response
poll_interval_seconds: 1.0
passive_wait_seconds: 0.5
```

### Exchange Minimums
- **exchange_min_size**: 0.061 SOL
- **exchange_min_notional**: $10.5
- **Critical**: Both maker AND hedger must meet these (fixed bug where hedger clips were too small)

---

## 🐛 Critical Bugs Fixed

### 1. Hedger Notional Bug (Nov 15, 2025)
**Problem**: Hedger clips (0.0105 SOL from PnL guard dampening) below exchange minimum notional ($10.5)
- Orders failing silently (code 21706)
- Inventory stuck at 0.093 SOL despite constant hedging
- Hedger completely ineffective

**Fix**: Added notional quantization to hedger (similar to maker)
- Ensures clips meet both size AND notional requirements
- Hedger now actually works and flattens inventory

**Status**: ✅ Fixed and deployed

### 2. Configuration Management (Nov 14, 2025)
**Problem**: Railway environment variables overriding config.yaml, causing confusion and context loss

**Fix**: Centralized all trading parameters in config.yaml
- Removed env overrides for trading params
- Only runtime toggles (dry_run, enabled) remain as env vars
- Single source of truth established

**Status**: ✅ Fixed and documented

### 3. Hedger Notional Check Logic (Nov 14, 2025)
**Problem**: Hedger blocked by AND logic - needed both units AND notional thresholds

**Fix**: Changed to OR logic - hedger executes if EITHER threshold exceeded

**Status**: ✅ Fixed

---

## 🏗️ Features Implemented

### Phase 1: Config-Only Quick Wins
- ✅ Tighter hedger params (trigger 0.008, target 0.0005)
- ✅ Wider spreads in downtrends (8 bps)
- ✅ Longer downtrend cooldowns (60s)
- ✅ Earlier PnL guard trigger (-$0.20)
- ✅ Wider spreads (13 bps base)

### Phase 2: Code Changes (Maker Engine)
- ✅ **Asymmetric Quoting**: Disable bids when long, disable asks when short (threshold: 0.01 SOL)
- ✅ **Inventory-Based Spread Widening**: +2 bps (0.01-0.02), +4 bps (0.02-0.03), +6 bps (>0.03)
- ✅ **Inventory-Based Size Reduction**: x0.75 (0.01-0.02), x0.50 (>0.02)
- ✅ **Order Quantization**: Ensures orders meet both size AND notional requirements

---

## 📈 What We Know Doesn't Work

1. **Large inventory builds** → Always result in losses (correlation = -1.0)
2. **Down-trends without protection** → Lose $13 per downtrend window
3. **High volatility periods** → Negative PnL
4. **Small hedger clips below notional** → Orders fail silently
5. **Config in multiple places** → Context loss and confusion

---

## 🎯 What We're Testing Now

### Current Hypothesis
- **Hedger fix should improve PnL** by actually flattening inventory
- **Inventory staying flatter** should reduce unrealized losses
- **Need 2-4 more hours** to see full impact

### Metrics to Monitor
1. **UI PnL trend** (primary): Should stabilize or improve
2. **Inventory levels**: Target < 0.008 SOL most of time
3. **PnL guard frequency**: Should decrease as inventory flattens
4. **Hedger execution**: Should execute when inventory > 0.008
5. **Large builds**: Should decrease (currently 2% of updates)

---

## 🔄 Fine-Tuning Opportunities

### If Loss Rate Doesn't Improve

**Option 1: Faster Hedger Response**
- `poll_interval_seconds`: 1.0 → 0.5 (catch builds earlier)
- `cooldown_seconds`: 1.5 → 1.0 (faster reaction)

**Option 2: Even Tighter Hedger**
- `trigger_units`: 0.008 → 0.006 (hedge even earlier)
- `target_units`: 0.0005 → 0.0003 (flatter target)

**Option 3: Wider Spreads**
- `spread_bps`: 13.0 → 14.0 or 15.0 (more edge per fill, fewer fills)

**Option 4: More Aggressive Downtrend Protection**
- `down_extra_spread_bps`: 8.0 → 10.0 (even wider in downtrends)
- `down_cooldown_seconds`: 60 → 90 (longer pauses)

---

## 📚 Documentation Structure

### This Document (MASTER_DOC.md)
- **Single source of truth** - Read this first when context is lost
- **Living document** - Update as we learn more
- **Current state snapshot** - Always reflects latest understanding

### Analysis Docs (docs/analysis/)
- Historical snapshots of specific analyses
- Deep dives into specific issues
- Reference material, but not primary source

### Config Docs (docs/)
- `CONFIG_STRATEGY.md`: How config management works
- `CONFIG_AUDIT.md`: Configuration audit findings

---

## 🔄 Iteration Strategy (When Context is Lost)

### Step 1: Read MASTER_DOC.md
- Understand current goal
- Review key learnings
- Check current configuration
- See what's working/not working

### Step 2: Check Current Status
```bash
# Check recent logs
railway logs --service lighter-bot --tail 1000 | grep -E "(inventory|hedger|PnL guard)" | tail -50

# Check inventory patterns
railway logs --service lighter-bot --tail 2000 | grep "position updated" | tail -100

# Check for errors
railway logs --service lighter-bot --tail 2000 | grep -E "(ERROR|CRITICAL|code=21706)"
```

### Step 3: Assess Performance
- **UI PnL**: Primary metric (realized + unrealized)
- **Inventory levels**: Should be mostly flat
- **PnL guard frequency**: Should decrease over time
- **Large builds**: Should be rare (< 5% of updates)

### Step 4: Make Decisions
- If loss rate improving → Continue monitoring
- If loss rate stable → Consider fine-tuning
- If loss rate worsening → More aggressive changes needed

### Step 5: Update MASTER_DOC.md
- Document new learnings
- Update current configuration
- Record what worked/didn't work

---

## 🚨 Important Concepts (Quick Reference)

### PnL Metrics
- **UI PnL**: Total PnL (realized + unrealized) - PRIMARY METRIC
- **FIFO Realized PnL**: True maker edge (accounting for cost basis)
- **CSV "realized_quote"**: MISLEADING - cash flow only, not true PnL

### Inventory Management
- **Inventory buildup = losses** (correlation = -1.0)
- **Target**: < 0.008 SOL most of time
- **Large builds**: Any build to > 0.05 SOL is concerning

### Hedger Behavior
- **Triggers at**: 0.008 SOL (or $4.0 notional, whichever comes first)
- **Targets**: 0.0005 SOL (nearly flat)
- **Max clip**: 0.03 SOL
- **Must meet**: Exchange minimum notional ($10.5)

### Maker Behavior
- **Asymmetric quoting**: Disables one side when inventory > 0.01 SOL
- **Spread widening**: Based on inventory and downtrends
- **Size reduction**: Based on inventory and PnL guard

---

## 🎓 Lessons Learned

### Configuration Management
- **Single source of truth** (config.yaml) prevents context loss
- **Environment variables** should only be runtime toggles
- **Version control** all trading parameters

### Inventory Control
- **Critical**: Inventory buildup causes losses faster than maker can profit
- **Solution**: Aggressive hedging + asymmetric quoting + spread widening
- **Cannot prevent all builds**: Fast fills happen, hedger reacts after

### Testing & Monitoring
- **Always check UI PnL** - CSV metrics can be misleading
- **Monitor inventory patterns** - flat inventory = good
- **Watch for order rejections** - silent failures are dangerous
- **Give changes time** - need 2-4 hours minimum to assess impact

### Iteration Process
- **Document everything** - context loss is real
- **One change at a time** - easier to isolate impact
- **Monitor before iterating** - don't change too fast
- **Update master doc** - keep single source of truth current

---

## 📝 Recent Changes History

### November 15, 2025
- ✅ Fixed hedger notional bug (critical)
- ✅ Tightened hedger params (trigger 0.008, target 0.0005, cooldown 1.5s)
- ✅ Created MASTER_DOC.md for context persistence

### November 14, 2025
- ✅ Fixed configuration management strategy
- ✅ Implemented Phase 2 features (asymmetric quoting, inventory-based adjustments)
- ✅ Fixed hedger notional check logic (OR instead of AND)

### November 13, 2025
- ✅ Initial profitability analysis
- ✅ Identified key learnings (downtrends, hedger costs, inventory correlation)
- ✅ Implemented Phase 1 config changes

---

## ❓ Open Questions / Future Work

1. **Will hedger fix improve PnL?** → Monitoring now (2-4 hours needed)
2. **Should we widen spreads further?** → Consider if loss rate doesn't improve
3. **Can we prevent large inventory builds?** → Fast fills make this hard
4. **Should we pause in high volatility?** → Need more data
5. **Can we predict downtrends earlier?** → Current 4 bps threshold seems good

---

## 📞 How to Use This Document

### When Starting Fresh (Context Lost)
1. Read this entire document
2. Check current status (logs, UI PnL)
3. Compare to expected state
4. Proceed with informed decisions

### When Iterating
1. Read relevant sections
2. Make changes
3. Update this document with learnings
4. Keep single source of truth current

### When Debugging
1. Check "Critical Bugs Fixed" section
2. Check "What We Know Doesn't Work"
3. Review recent changes
4. Add new findings to this document

---

**Remember**: This is a living document. Update it as we learn more, so the next time context is lost, we can recover quickly.

