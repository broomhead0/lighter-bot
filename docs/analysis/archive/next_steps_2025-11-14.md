# Next Steps for Profitability - November 14, 2025

## Current State Analysis

**Observations from logs:**
- PnL guard is engaging (spread widening to 17-21 bps) ✅
- Hedger is active and trying to flatten inventory ✅
- Inventory still building up (0.031-0.045 SOL) despite hedger ⚠️
- Maker is still placing orders even with inventory ⚠️

**Key Issues:**
1. **Inventory buildup**: Even with tighter hedger params, inventory accumulates (0.031-0.045 SOL)
2. **Maker not responsive to inventory**: Maker continues quoting both sides even when inventory exists
3. **PnL guard reactive, not preventive**: Guard engages after losses, doesn't prevent them

## What We've Already Tried

✅ **Implemented (from profitability_analysis_2025-11-13.md):**
- More aggressive downtrend handling (down_threshold: 4, down_cooldown: 60s, down_extra_spread: 8bps)
- Reduced hedger costs (trigger: 0.015, target: 0.003, max_clip: 0.04, passive_wait: 0.5s)
- Lowered inventory_soft_cap to 0.05
- PnL guard enabled (widens spread +4bps, reduces size x0.85 when FIFO PnL < -$0.50 for 2 consecutive checks)
- Dynamic regime switching
- Hedger safeguard (emergency flattening when guard blocks)

⚠️ **Still losing money** - Need more aggressive changes

## Proposed Next Steps (Priority Order)

### 1. **Asymmetric Quoting (HIGH PRIORITY)**
**Problem**: Maker quotes both sides even when inventory exists, causing inventory buildup

**Solution**: Make maker asymmetric based on inventory:
- When long inventory > 0.01 SOL: Reduce/eliminate bid size, keep asking (sell to flatten)
- When short inventory < -0.01 SOL: Reduce/eliminate ask size, keep bidding (buy to flatten)
- When flat: Quote both sides normally

**Impact**: Prevents maker from adding to inventory position, works WITH hedger instead of against it

**Implementation**:
```yaml
maker:
  inventory_asymmetric: true  # New config option
  asymmetric_threshold_units: 0.01  # Threshold to trigger asymmetric quoting
```

### 2. **More Aggressive PnL Guard (HIGH PRIORITY)**
**Problem**: PnL guard only triggers after losses accumulate (-$0.50 floor, 2 consecutive checks)

**Solution**:
- Lower realized_floor from -$0.50 to -$0.20 (trigger earlier)
- Reduce trigger_consecutive from 2 to 1 (trigger immediately)
- Increase widen_bps from 4.0 to 6.0 (wider spreads when engaged)
- Increase max_extra_bps from 8.0 to 10.0 (allow more aggressive widening)

**Impact**: Responds faster to losses, prevents deeper drawdowns

**Config Changes**:
```yaml
maker:
  pnl_guard:
    realized_floor_quote: -0.20  # Trigger earlier (was -0.50)
    trigger_consecutive: 1  # Trigger immediately (was 2)
    widen_bps: 6.0  # Wider spreads (was 4.0)
    max_extra_bps: 10.0  # Allow more aggressive widening (was 8.0)
```

### 3. **Inventory-Based Spread Widening (MEDIUM PRIORITY)**
**Problem**: Spreads don't widen as inventory builds, leading to more fills that add to inventory

**Solution**: Add spread bonus based on inventory size:
- +0 bps when inventory < 0.01 SOL (flat)
- +2 bps when inventory 0.01-0.02 SOL
- +4 bps when inventory 0.02-0.03 SOL
- +6 bps when inventory > 0.03 SOL

**Impact**: Makes fills less attractive as inventory builds, naturally slows down maker

**Implementation**: Add to maker_engine.py spread calculation

### 4. **Tighter Hedger Parameters (MEDIUM PRIORITY)**
**Current**: trigger_units: 0.015, target_units: 0.003, max_clip_units: 0.04

**Proposed**:
- Lower trigger_units: 0.010 (hedge even earlier)
- Lower target_units: 0.001 (nearly flat)
- Reduce max_clip_units: 0.03 (smaller clips, more frequent but cheaper)
- Reduce cooldown_seconds: 2.0 (faster response)

**Impact**: Flattens inventory faster, prevents larger builds

**Config Changes**:
```yaml
hedger:
  trigger_units: 0.010  # Hedge earlier (was 0.015)
  target_units: 0.001  # Nearly flat (was 0.003)
  max_clip_units: 0.03  # Smaller clips (was 0.04)
  cooldown_seconds: 2.0  # Faster response (was 3.0)
```

### 5. **Reduce Base Maker Size When Inventory Exists (MEDIUM PRIORITY)**
**Problem**: Maker continues with full size even when inventory is building

**Solution**: Reduce maker base_size when inventory > threshold:
- Size x1.0 when inventory < 0.01 SOL
- Size x0.75 when inventory 0.01-0.02 SOL
- Size x0.50 when inventory > 0.02 SOL

**Impact**: Naturally slows maker down as inventory builds, prevents adding to position

### 6. **Wider Base Spread (LOW PRIORITY - Test if others don't work)**
**Current**: spread_bps: 12.0

**Proposed**: spread_bps: 14.0 or 15.0

**Impact**: More edge per fill, fewer fills (but also less volume)

**Tradeoff**: Less trading volume vs more edge per trade

## Implementation Plan

### Phase 1: Quick Wins (Implement First)
1. **More aggressive PnL guard** (config change only)
2. **Tighter hedger parameters** (config change only)
3. Deploy and monitor for 1-2 hours

### Phase 2: Code Changes (If Phase 1 insufficient)
1. **Asymmetric quoting** (requires code change in maker_engine.py)
2. **Inventory-based spread widening** (requires code change)
3. **Inventory-based size reduction** (requires code change)
4. Deploy and monitor

### Phase 3: Fine-tuning (If still losing)
1. Consider wider base spread
2. More aggressive downtrend handling
3. Run regime analysis again with new data

## Expected Impact

If all changes work:
- **Inventory control**: Should stay < 0.01 SOL most of the time
- **PnL guard**: Should trigger faster and prevent deeper losses
- **Hedger costs**: Should decrease (smaller, more frequent clips)
- **Overall PnL**: Should move from negative to neutral/slightly positive

## Metrics to Track

After deployment, monitor:
1. **FIFO realized PnL** (target: neutral or positive)
2. **Average inventory** (target: < 0.01 SOL)
3. **PnL guard activation frequency** (should see it engage less as we prevent losses earlier)
4. **Hedger clip sizes** (target: mostly < 0.03 SOL)
5. **Maker spread** (should see wider spreads when inventory/guard active)

## Next Actions

1. ✅ Document current state and findings
2. ⏳ Implement Phase 1 changes (config only)
3. ⏳ Deploy and monitor for 1-2 hours
4. ⏳ If still losing, implement Phase 2 (code changes)
5. ⏳ Run regime analysis after 4-6 hours of data

