# Simplification Plan: Start from Scratch, Add Back Incrementally

**Date**: November 15, 2025  
**Goal**: Simplify bot to basics, then add features back incrementally with testing at each step

---

## 🎯 Strategy Overview

1. **Extract complex features** into isolated modules/classes
2. **Create simplified core** with minimal features
3. **Build feature flags** for easy enable/disable
4. **Test each feature independently** before adding next
5. **Keep old code** but disable by default

---

## 📋 Phase 0: Preparation (Extract & Isolate)

### 0.1 Create Feature Modules (Keep Old Logic)
Extract complex subsystems into separate classes that can be enabled/disabled:

**New files to create:**
```
modules/features/
  ├── __init__.py
  ├── volatility_adjustments.py    # EMA-based volatility logic
  ├── trend_filter.py               # Trend detection with EMA
  ├── regime_switcher.py            # Aggressive/defensive profiles
  ├── pnl_guard.py                  # Reactive PnL-based adjustments
  ├── inventory_adjustments.py      # Tiered spread/size adjustments
  └── hedger_passive_logic.py       # Passive/aggressive hedger logic
```

**Approach:**
- Copy current logic into these modules
- Make them optional/pluggable
- Each module has `enabled` flag and clean interface
- No behavior change - just reorganization

### 0.2 Simplify Core Modules
Strip down `maker_engine.py` and `hedger.py` to minimal implementations:

**maker_engine.py (Simplified)**
```python
class MakerEngine:
    def __init__(self, config, state, trading_client, features=None):
        # Core only
        self.spread_bps = config['spread_bps']
        self.size = config['size']
        self.mid = None
        
        # Optional features (None if disabled)
        self.volatility_feature = features.get('volatility') if features else None
        self.trend_feature = features.get('trend') if features else None
        self.regime_feature = features.get('regime') if features else None
        self.pnl_guard_feature = features.get('pnl_guard') if features else None
        self.inventory_feature = features.get('inventory') if features else None
    
    def _calculate_spread(self):
        spread = self.spread_bps  # Base spread
        
        # Apply features if enabled (in order)
        if self.trend_feature and self.trend_feature.enabled:
            spread += self.trend_feature.get_spread_adjustment()
        
        if self.volatility_feature and self.volatility_feature.enabled:
            spread *= self.volatility_feature.get_spread_multiplier()
        
        if self.inventory_feature and self.inventory_feature.enabled:
            spread += self.inventory_feature.get_spread_adjustment()
        
        if self.pnl_guard_feature and self.pnl_guard_feature.enabled:
            spread += self.pnl_guard_feature.get_spread_adjustment()
        
        if self.regime_feature and self.regime_feature.enabled:
            spread += self.regime_feature.get_extra_spread()
        
        return spread
```

**hedger.py (Simplified)**
```python
class Hedger:
    def __init__(self, config, state, trading_client, features=None):
        # Core only
        self.trigger_units = config['trigger_units']
        self.target_units = config['target_units']
        self.max_clip = config['max_clip_units']
        
        # Optional features
        self.passive_feature = features.get('passive') if features else None
    
    async def hedge_if_needed(self):
        inventory = self.state.get_inventory()
        
        if abs(inventory) < self.trigger_units:
            return  # No hedge needed
        
        clip_size = self._calculate_clip(inventory)
        
        # Use passive logic if enabled, else direct limit order
        if self.passive_feature and self.passive_feature.enabled:
            await self.passive_feature.try_passive_fill(clip_size)
        else:
            await self._place_limit_order(clip_size)
```

### 0.3 Feature Flag System
Add to config.yaml:
```yaml
features:
  enabled: []  # List of features to enable: ['volatility', 'trend', etc.]
  
  # Feature-specific configs (only used if enabled)
  volatility:
    enabled: false  # Disable by default
    # ... all volatility params
  
  trend:
    enabled: false  # Disable by default
    # ... all trend params
  
  regime:
    enabled: false
  
  pnl_guard:
    enabled: false
  
  inventory:
    enabled: false
  
  hedger_passive:
    enabled: false
```

### 0.4 Testing Infrastructure
Create simple test harness:
```python
# scripts/test_feature_incremental.py
"""
Test bot with different feature combinations.
Usage: python scripts/test_feature_incremental.py --features "base" --hours 4
"""

def test_configuration(features_list, duration_hours):
    # Create config with only specified features enabled
    # Run bot for duration
    # Collect metrics
    # Compare to baseline
    pass
```

---

## 📋 Phase 1: Minimal Viable Bot (Baseline)

### 1.1 Core Features Only
**Enabled:**
- ✅ Basic maker (fixed spread, quote around mid)
- ✅ Simple hedger (hedge when > threshold, clip to flat)
- ✅ Exchange minimum validation
- ✅ Basic asymmetric quoting (disable one side if inventory > 0.01)

**Disabled:**
- ❌ All volatility adjustments
- ❌ All trend detection
- ❌ Regime switching
- ❌ PnL guard
- ❌ Tiered inventory adjustments
- ❌ Hedger passive logic
- ❌ Emergency modes
- ❌ Multiple cooldowns

### 1.2 Configuration
```yaml
maker:
  spread_bps: 15.0  # Conservative start
  size: 0.064
  # No volatility, trend, regime, pnl_guard configs
  
  # Simple inventory awareness
  asymmetric_quoting_threshold: 0.01  # Disable side if > this

hedger:
  trigger_units: 0.008
  target_units: 0.0  # Flat
  max_clip_units: 0.05
  cooldown_seconds: 2.0
  # No passive logic, emergency modes

features:
  enabled: []  # Empty - base only
```

### 1.3 Testing Criteria
**Run for 24-48 hours and measure:**
- ✅ PnL trend (should be stable or improving)
- ✅ Inventory levels (should stay < 0.01 most of time)
- ✅ Order rejection rate (should be 0%)
- ✅ Hedger execution frequency (should hedge when needed)
- ✅ Fill rate (maker should get fills)

**Success Criteria:**
- Loss rate ≤ -$0.20/hour (better than current -$0.25/hour)
- Inventory flat 90%+ of time
- No order rejections
- Bot runs stably

**If baseline fails:**
- Increase spread (15 → 18 → 20 bps)
- Tighten hedger (0.008 → 0.006 → 0.005)
- Adjust size if needed

---

## 📋 Phase 2: Add Back Features One by One

### 2.1 Feature 1: Simple Trend Protection
**What**: Price change detection (NOT EMA), widen spread in downtrends

**Implementation:**
```python
# modules/features/trend_filter.py
class SimpleTrendFilter:
    def __init__(self, config):
        self.enabled = config.get('enabled', False)
        self.lookback_seconds = config.get('lookback_seconds', 60)  # Simple, not EMA
        self.down_threshold_bps = config.get('down_threshold_bps', 6)
        self.extra_spread_bps = config.get('extra_spread_bps', 5)
        self.price_history = deque(maxlen=100)
    
    def update(self, mid_price, timestamp):
        if not self.enabled:
            return
        self.price_history.append((timestamp, mid_price))
    
    def get_spread_adjustment(self):
        if not self.enabled or len(self.price_history) < 2:
            return 0
        
        # Simple: price change over lookback window
        oldest_price = self.price_history[0][1]
        current_price = self.price_history[-1][1]
        price_change_bps = (current_price - oldest_price) / oldest_price * 10000
        
        if price_change_bps < -self.down_threshold_bps:
            return self.extra_spread_bps
        return 0
```

**Config:**
```yaml
features:
  enabled: ['trend']

trend:
  enabled: true
  lookback_seconds: 60  # Simple time window
  down_threshold_bps: 6
  extra_spread_bps: 5
```

**Testing:**
- Run 24-48 hours
- Compare to baseline:
  - PnL during downtrends (should improve)
  - Overall PnL (should be better or same)
  - Fill rate (might decrease slightly)

**Success Criteria:**
- PnL improved OR stable
- Downtrend periods less costly
- No regressions in other metrics

**If fails:**
- Adjust thresholds (6 bps → 8 bps, 5 bps → 7 bps)
- Or disable and move on

---

### 2.2 Feature 2: Simple Inventory Adjustments
**What**: Binary inventory adjustments (above/below threshold, not tiers)

**Implementation:**
```python
# modules/features/inventory_adjustments.py
class SimpleInventoryAdjustments:
    def __init__(self, config):
        self.enabled = config.get('enabled', False)
        self.threshold = config.get('threshold', 0.015)  # Single threshold
        self.spread_adjustment_bps = config.get('spread_adjustment_bps', 3)
        self.size_multiplier = config.get('size_multiplier', 0.75)
    
    def get_spread_adjustment(self, inventory):
        if not self.enabled:
            return 0
        if abs(inventory) > self.threshold:
            return self.spread_adjustment_bps
        return 0
    
    def get_size_multiplier(self, inventory):
        if not self.enabled:
            return 1.0
        if abs(inventory) > self.threshold:
            return self.size_multiplier
        return 1.0
```

**Testing:**
- Run 24-48 hours
- Monitor: inventory levels, spread when above threshold

**Success Criteria:**
- Inventory stays lower on average
- PnL improved or stable

---

### 2.3 Feature 3: PnL Guard (Simplified)
**What**: Wider spreads when losing, but less reactive

**Implementation:**
```python
# modules/features/pnl_guard.py
class SimplePnLGuard:
    def __init__(self, config):
        self.enabled = config.get('enabled', False)
        self.threshold = config.get('threshold', -0.50)  # Larger threshold
        self.widen_bps = config.get('widen_bps', 4)
        self.window_seconds = config.get('window_seconds', 600)  # 10 min, not 5
    
    def check_and_adjust(self, realized_pnl):
        if not self.enabled:
            return 0
        if realized_pnl < self.threshold:
            return self.widen_bps
        return 0
```

**Testing:**
- Run 48 hours
- Monitor: trigger frequency, impact on recovery

**Success Criteria:**
- Triggers less frequently than before
- Helps recovery from losses
- No regressions

---

### 2.4 Feature 4: Hedger Passive Logic
**What**: Try passive fills before aggressive (keep simple)

**Testing:**
- Measure: cost per hedge, fill time

**Success Criteria:**
- Lower hedging costs
- Acceptable fill times

---

## 📋 Testing Methodology

### For Each Phase/Feature:

1. **Setup**
   - Enable feature(s) via config
   - Deploy to Railway
   - Verify config loaded correctly

2. **Run**
   - 24-48 hours minimum
   - Monitor logs for errors
   - Check UI PnL every 4-6 hours

3. **Collect Metrics**
   - UI PnL (primary)
   - Inventory distribution (should be flat)
   - Fill rate
   - Hedger execution frequency
   - Order rejection rate
   - Spread distribution (log samples)

4. **Compare**
   - Before vs after PnL rate
   - Before vs after inventory levels
   - Before vs after fill rate

5. **Decision**
   - **Keep**: If improved or stable, add to baseline
   - **Tune**: If close, adjust parameters and retest
   - **Remove**: If worse, disable and move on

### Metrics Collection
```python
# scripts/collect_metrics.py
"""
Collect metrics from logs and positions.jsonl for comparison.
Usage: python scripts/collect_metrics.py --start <timestamp> --end <timestamp>
"""

def collect_metrics(start_time, end_time):
    return {
        'pnl_rate_per_hour': ...,
        'inventory_distribution': ...,
        'fill_rate': ...,
        'hedger_frequency': ...,
        'order_rejections': ...,
        'avg_spread': ...,
        'max_inventory': ...,
        'time_flat_pct': ...,
    }
```

---

## 📋 Implementation Steps

### Step 1: Create Feature Modules (No Behavior Change)
1. Create `modules/features/` directory
2. Extract volatility logic → `volatility_adjustments.py`
3. Extract trend logic → `trend_filter.py`
4. Extract regime logic → `regime_switcher.py`
5. Extract PnL guard logic → `pnl_guard.py`
6. Extract inventory adjustments → `inventory_adjustments.py`
7. Extract hedger passive logic → `hedger_passive_logic.py`
8. All features disabled by default (enabled=False)

### Step 2: Refactor Core Modules
1. Simplify `maker_engine.py` to core only
2. Add feature injection points
3. Simplify `hedger.py` to core only
4. Add feature injection points
5. Update `core/main.py` to load features from config
6. Test: Bot should run identically to before (all features still work)

### Step 3: Create Baseline Config
1. Create `config.baseline.yaml` with minimal features
2. All complex features disabled
3. Simple parameters only

### Step 4: Test Baseline
1. Deploy baseline config
2. Run 24-48 hours
3. Collect metrics
4. Document baseline performance

### Step 5: Add Features One by One
1. Enable one feature
2. Test for 24-48 hours
3. Compare to baseline
4. Make decision (keep/tune/remove)
5. If kept, add to baseline and continue

---

## 📋 Success Metrics

### Baseline Success:
- ✅ Loss rate ≤ -$0.20/hour
- ✅ Inventory flat 90%+ of time
- ✅ No order rejections
- ✅ Stable operation

### Feature Addition Success:
- ✅ PnL improved OR stable
- ✅ No regressions in other metrics
- ✅ Feature clearly helps or clearly doesn't
- ✅ Maintains simplicity

---

## 📋 Rollback Plan

### If Baseline Fails:
1. Re-enable all features (safety net)
2. Analyze what went wrong
3. Adjust baseline parameters
4. Retry

### If Feature Addition Fails:
1. Disable that feature
2. Continue with next feature
3. Document why it failed
4. Can retry later with different parameters

### Code Safety:
- All old code preserved in feature modules
- Can re-enable anytime via config
- Git history preserved
- No code deletion, only reorganization

---

## 📋 Timeline Estimate

- **Phase 0 (Extract)**: 2-3 hours
- **Phase 1 (Baseline)**: 1 hour deploy + 48 hours testing
- **Phase 2 (Features)**: 1 hour per feature + 24-48 hours testing each
  - 6 features × 2 days = ~12 days
- **Total**: ~2-3 weeks for full iteration

**Faster path**: Test baseline for 24 hours, then add 2-3 most promising features

---

## ❓ Questions Before Starting

1. **Baseline spread**: Start at 15 bps (conservative) or 13 bps (current)?
2. **Testing duration**: 24 hours minimum or 48 hours?
3. **Priority features**: Which features to test first? (trend, inventory, PnL guard?)
4. **Rollback threshold**: If baseline loses more than current (-$0.25/hr), rollback immediately?

---

## 📝 Next Steps (After Review)

1. ✅ Review and approve plan
2. ⏳ Implement Phase 0 (extract features)
3. ⏳ Test Phase 0 (verify no behavior change)
4. ⏳ Implement Phase 1 (baseline)
5. ⏳ Deploy and test baseline
6. ⏳ Iterate through Phase 2 (add features)

---

## 🎯 Expected Outcome

**After simplification:**
- Cleaner, more maintainable codebase
- Easier to reason about and tune
- Features can be enabled/disabled independently
- Clear understanding of what helps vs hurts
- Path to profitability through incremental improvement

**Codebase metrics:**
- maker_engine.py: 1000+ → 400 lines
- hedger.py: 700+ → 250 lines  
- config.yaml: 89 → 50 lines (base) + feature configs
- Total features: 7 modular, testable components

