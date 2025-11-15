# Simplification Analysis - Back to Basics

**Date**: November 15, 2025  
**Context**: After a week of iteration, still losing ~$0.25/hour. User wants to simplify and go back to basics, noting that simpler trend-following algorithms are more profitable.

---

## 📊 What We've Built (Current Complexity)

### Core Modules (14 total)
1. **maker_engine.py** - Core quoting logic (~1000+ lines)
   - Base quoting
   - Volatility adjustments (EMA-based)
   - Trend filtering
   - Inventory-based adjustments
   - Asymmetric quoting
   - Regime switching (aggressive/defensive)
   - PnL guard integration
   - Order quantization

2. **hedger.py** - Inventory management (~700+ lines)
   - Trigger-based hedging
   - Passive/aggressive fills
   - Emergency flattening
   - Guard-aware clipping
   - Multiple cooldown timers
   - Retry logic with backoff

3. **account_listener.py** - Position tracking (~600+ lines)
   - WebSocket subscription
   - Fill processing
   - FIFO PnL calculation
   - Position update tracking
   - Metrics ledger integration

4. **market_data_listener.py** - Market data (~400+ lines)
   - WebSocket connection
   - Synthetic fallback
   - Mid price tracking
   - Market stats aggregation

5. **funding_optimizer.py** - Market selection (unused/disabled)
6. **mean_reversion_trader.py** - Alternative strategy (disabled)
7. **chaos_injector.py** - Testing (disabled)
8. **replay_sim.py** - Testing (disabled)
9. **self_trade_guard.py** - Safety checks
10. **telemetry.py** - Metrics
11. **alert_manager.py** - Notifications
12. **synthetic_mid_feeder.py** - Fallback
13. **raw_replayer.py** - Testing
14. **mock_metrics.py** - Testing

### Configuration Complexity
- **89 lines** of config.yaml with:
  - Volatility subsystem (10 params)
  - Trend subsystem (8 params)
  - Regime subsystem (6 params)
  - PnL guard (8 params)
  - Hedger (20+ params)
  - Maker (15+ params)

### Features Added This Week
1. **Asymmetric Quoting** - Disable one side when inventory > threshold
2. **Inventory-Based Spread Widening** - 3-tier system
3. **Inventory-Based Size Reduction** - 2-tier system
4. **Volatility Adjustments** - EMA-based with pause/resume thresholds
5. **Trend Filtering** - Lookback with downtrend protection
6. **Regime Switching** - Aggressive/defensive profiles
7. **PnL Guard** - Reactive spread widening on losses
8. **Order Quantization** - Size and notional checks
9. **Hedger Improvements** - Passive fills, emergency mode, guard integration

---

## ✅ What's Actually Helping

### 1. **Hedger Fix (Critical)**
- **What**: Fixed hedger notional bug - orders were failing silently
- **Impact**: HIGH - Hedger actually works now
- **Complexity**: LOW - Just a bug fix
- **Keep?**: ✅ YES - Essential

### 2. **Inventory Control Awareness**
- **What**: Learned that inventory buildup = losses (correlation -1.0)
- **Impact**: HIGH - Core understanding
- **Complexity**: LOW - Just a parameter adjustment
- **Keep?**: ✅ YES - But simplify implementation

### 3. **Config Strategy Fix**
- **What**: Single source of truth (config.yaml)
- **Impact**: HIGH - Prevents confusion
- **Complexity**: LOW
- **Keep?**: ✅ YES

### 4. **Exchange Minimum Awareness**
- **What**: Must meet both size AND notional minimums
- **Impact**: HIGH - Prevents order rejections
- **Complexity**: LOW - Just validation
- **Keep?**: ✅ YES

### 5. **Basic Spread Widening**
- **What**: Wider spreads in downtrends (8 bps extra)
- **Impact**: MEDIUM - Helps avoid bad fills
- **Complexity**: LOW - One parameter
- **Keep?**: ✅ MAYBE - Simplify to single threshold

---

## ❌ What's NOT Helping (Added Complexity)

### 1. **Regime Switching**
- **What**: Aggressive/defensive profiles based on volatility
- **Impact**: LOW - Hard to measure, adds complexity
- **Complexity**: HIGH - Multiple thresholds, state machine
- **Evidence**: No clear improvement, regime state unclear
- **Remove?**: ✅ YES - Simplify to single behavior

### 2. **Volatility EMA Subsystem**
- **What**: EMA-based volatility with pause/resume thresholds
- **Impact**: LOW - Low-vol pause disabled, high-vol pause at 30bps (rare)
- **Complexity**: HIGH - EMA calculation, multiple thresholds
- **Evidence**: Internal EMA lags external vol, causes confusion
- **Remove?**: ✅ YES - Replace with simple lookback or remove

### 3. **Inventory-Based Tiered Adjustments**
- **What**: 3-tier spread widening, 2-tier size reduction
- **Impact**: MEDIUM - Helps but complicated
- **Complexity**: MEDIUM - Multiple thresholds, conditional logic
- **Evidence**: Works but could be simpler
- **Simplify?**: ✅ YES - Single threshold, binary on/off

### 4. **PnL Guard Reactive System**
- **What**: Spread widening when realized PnL < -$0.20
- **Impact**: MEDIUM - Helps but triggers frequently
- **Complexity**: MEDIUM - Window tracking, state management
- **Evidence**: Engaging every 15s, might be too reactive
- **Simplify?**: ✅ MAYBE - Larger threshold, less aggressive

### 5. **Trend Lookback System**
- **What**: 45s EMA lookback with downtrend detection
- **Impact**: MEDIUM - Helps but complex
- **Complexity**: MEDIUM - EMA calculation, threshold detection
- **Evidence**: 4bps threshold helps, but EMA adds lag
- **Simplify?**: ✅ YES - Simple price change over fixed window

### 6. **Hedger Passive/Aggressive Logic**
- **What**: Try passive first, then aggressive with multiple timeouts
- **Impact**: LOW - Complex, hard to measure
- **Complexity**: HIGH - Multiple timers, state management
- **Evidence**: Might save a bit on fees but adds complexity
- **Simplify?**: ✅ YES - Just post limit orders, no passive logic

### 7. **Asymmetric Quoting**
- **What**: Disable bids when long, asks when short
- **Impact**: MEDIUM - Helps but adds complexity
- **Complexity**: LOW-MEDIUM - Conditional logic
- **Evidence**: Works but overlaps with hedger
- **Keep?**: ✅ MAYBE - Simple enough to keep

---

## 💡 What Simple Trend Bot Does (Reference)

Based on user's comment: "my trend following algos on the trend trading bot are much simpler and seem to be more profitable"

**Simple approach likely includes:**
- ✅ Basic spread calculation (no tiers)
- ✅ Simple trend detection (price change, not EMA)
- ✅ Basic inventory control (hedge when > threshold)
- ✅ No regime switching
- ✅ No volatility adjustments
- ✅ No PnL guard
- ✅ No complex cooldowns

**Key difference**: Fewer moving parts = easier to reason about and tune

---

## 🎯 Simplified Architecture Proposal

### Keep (Core Essentials)
1. **Basic Maker**
   - Fixed spread (configurable)
   - Place quotes around mid
   - Basic order validation (size/notional minimums)

2. **Simple Hedger**
   - Hedge when inventory > threshold
   - Clip to target (flat or small)
   - Basic cooldown

3. **Basic Trend Protection** (Optional)
   - If price down > X bps, widen spread or pause
   - Simple price change (not EMA)

4. **Inventory Awareness** (Keep but simplify)
   - Asymmetric quoting (disable one side when long/short)
   - Single threshold (not 3 tiers)

### Remove/Disable
1. ❌ Regime switching
2. ❌ Volatility EMA system
3. ❌ PnL guard reactive system
4. ❌ Tiered inventory adjustments
5. ❌ Hedger passive/aggressive logic
6. ❌ Multiple cooldown timers
7. ❌ Emergency modes
8. ❌ Guard integration complexity

### Simplify
1. **Maker Engine**: ~1000 lines → ~300-400 lines
   - Remove volatility subsystem
   - Remove regime switching
   - Remove PnL guard integration
   - Simplify trend to price change
   - Simplify inventory to binary (above/below threshold)

2. **Hedger**: ~700 lines → ~200-300 lines
   - Remove passive/aggressive logic
   - Remove emergency modes
   - Remove guard integration
   - Simple: poll, check threshold, clip if needed

3. **Config**: ~89 lines → ~40-50 lines
   - Remove volatility config (10 params)
   - Remove regime config (6 params)
   - Remove PnL guard config (8 params)
   - Keep: spread, size, hedger params, basic trend

---

## 📋 Action Plan

### Phase 1: Remove Complex Features (No Behavior Change)
1. Disable regime switching in config
2. Disable volatility adjustments in config
3. Disable PnL guard in config
4. Test: Bot should still run, just simpler

### Phase 2: Simplify Remaining Features
1. Simplify trend detection (EMA → price change)
2. Simplify inventory adjustments (tiers → binary)
3. Simplify hedger (remove passive logic)
4. Test: Verify behavior still reasonable

### Phase 3: Code Cleanup
1. Remove unused code paths
2. Remove commented-out logic
3. Simplify conditionals
4. Reduce file sizes

### Phase 4: Re-Tune Simple System
1. Start with conservative spreads (15-20 bps)
2. Tight hedger (trigger at 0.005-0.008)
3. Simple trend protection (if down > 6 bps, widen 5 bps)
4. Monitor and tune one thing at a time

---

## 🎓 Key Insights

### What We Learned
1. **Inventory buildup = losses** (correlation -1.0) ← KEEP THIS
2. **Hedger must actually work** (fixed bug) ← KEEP THIS
3. **Downtrends are costly** ← KEEP simple protection
4. **Complex systems are hard to tune** ← REMOVE complexity

### What Didn't Work
1. **Regime switching** - Too many states, unclear when it helps
2. **Volatility EMA** - Lags reality, causes confusion
3. **PnL guard** - Too reactive, triggers constantly
4. **Tiered systems** - Hard to tune, unclear benefits

### Principle: **Simple First, Complex Later**
- Start with basic maker + hedger
- Add ONE feature at a time
- Measure impact before adding more
- Only add complexity if simple doesn't work

---

## ❓ Questions for User

1. **What parameters work in your trend bot?**
   - Spread?
   - Hedge trigger?
   - Trend detection method?

2. **Should we strip down to absolute basics first?**
   - Just maker + hedger, nothing else?
   - Or keep basic trend protection?

3. **What's your priority?**
   - Minimum viable profitable bot?
   - Or clean, maintainable codebase?

4. **Testing approach?**
   - Start from scratch with simple version?
   - Or disable features incrementally?

---

## 📝 Next Steps (Awaiting User Input)

1. ✅ Analysis complete
2. ⏳ User review and direction
3. ⏳ Implement simplifications
4. ⏳ Test simple version
5. ⏳ Tune simple system
6. ⏳ Add back complexity ONLY if needed

