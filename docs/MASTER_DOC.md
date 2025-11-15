# MASTER DOCUMENT - Lighter Bot Profitability Journey

**Last Updated**: November 15, 2025
**Purpose**: Single source of truth for bot state, learnings, and iteration strategy
**When Context is Lost**: Read this document first to get back up to speed

---

## 🎯 Current Goal

**Simplify and rebuild incrementally** - After a week of iteration, still losing ~-$0.25/hour. Strategy changed to:
1. Strip down to minimal viable bot (baseline)
2. Add features back one by one with testing
3. Only keep features that clearly help

**Key Insight**: Simpler trend-following bot is more profitable. Too much complexity makes it hard to tune and reason about.

---

## 🔄 Current Strategy: Simplification & Incremental Testing

### Decision (Nov 15, 2025)
After comprehensive analysis, we're starting from scratch with a simplified baseline, then adding features back incrementally.

**Plan**: See `docs/SIMPLIFICATION_PLAN.md` for full details

**Decisions Made**:
- **Baseline spread**: 15 bps (conservative start)
- **Testing duration**: 24 hours minimum (48 hours preferred)
- **Priority features**: Trend → Inventory → PnL Guard
- **Rollback threshold**: If baseline loses > -$0.30/hr, rollback immediately

### Implementation Phases

**Phase 0: Extract Features** (In Progress - 50% complete)
- Extract complex logic into `modules/features/` modules
- Make all features optional/pluggable
- No behavior change - just reorganization
- **Progress**:
  - ✅ Trend filter extracted (240 lines) + integrated
  - ✅ Inventory adjustments extracted (140 lines) + integrated
  - ✅ PnL guard extracted (180 lines) + integrated
  - ⏳ Remaining: Volatility, Regime, Hedger passive (3 features)
  - Total: 1888 lines to refactor

**Phase 1: Minimal Baseline** (Next)
- Core only: basic maker, simple hedger
- All complex features disabled
- Test 24-48 hours

**Phase 2: Add Features Incrementally** (Future)
- Add one feature at a time
- Test each for 24-48 hours
- Keep only if improves PnL

---

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

### Step 2: Post-Phase Testing Protocol ✅
**CRITICAL**: After completing each phase/feature extraction:
1. **Monitor logs for 1 minute** - Watch for errors, exceptions, warnings
2. **If errors found** - Fix them immediately
3. **Monitor again for 1 minute** - Verify fixes worked
4. **Repeat until clean** - No errors for full 1 minute period
5. **Then proceed** - Only continue to next phase if logs are clean

**Why**: Catch integration issues early before they cause problems in production

**How to monitor**:
```bash
railway logs --service lighter-bot --tail 500 | grep -E "(ERROR|CRITICAL|Exception|Traceback|failed|error)" | head -20
```

### Step 3: Check Current Status
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

### November 15, 2025 - Simplification Strategy
- ✅ Comprehensive analysis of what helps vs hurts (see `docs/SIMPLIFICATION_ANALYSIS.md`)
- ✅ Created simplification plan: start from scratch, add back incrementally (see `docs/SIMPLIFICATION_PLAN.md`)
- ✅ Decision: Strip to baseline, then add features one by one with testing
- ✅ Phase 0: Extract features into modules (preserve old logic, make optional)
- 🔄 **Status**: Implementing Phase 0 (extraction)

### November 15, 2025 - Earlier
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

### 📊 Time-Based PnL Analysis ✅
**Status**: Script created and initial analysis complete

**Script**: `scripts/analyze_time_based_pnl.py`
- Analyzes PnL trends by day of week, hour of day, time periods, and market hours
- Outputs CSV data and markdown report
- Initial analysis shows limited patterns (mostly Friday data)

**Usage**:
```bash
python3 scripts/analyze_time_based_pnl.py --input data/analysis/pnl_5m.csv
```

**Next Steps**:
- Run analysis after collecting more data (ideally 7+ days)
- Compare NY hours (9am-4pm ET) vs overnight vs weekend performance
- Identify optimal trading windows and potentially pause/scale during unprofitable periods

**Purpose**: Identify optimal trading windows and potentially pause/scale during unprofitable periods.

### 📥 Tracking Position Updates (Source of Truth) ✅
**Status**: Implemented in `account_listener.py`

**How it works**:
- Exchange sends position updates via WebSocket with `realized_pnl` and `unrealized_pnl`
- These values match the UI PnL exactly (source of truth!)
- `account_listener.py` logs each position update to `data/metrics/positions.jsonl`
- Much simpler and more reliable than reconstructing PnL from 200k+ API trades
- **No API calls needed** - we already receive this data via WebSocket
- **No format conversion** - we log the PnL values directly from exchange
- **Minimal overhead** - just append JSONL lines as updates arrive

**Format**: JSONL with timestamp, market, position, realized_pnl, unrealized_pnl, total_pnl

**Usage for Analysis**:
- As the bot runs, `data/metrics/positions.jsonl` accumulates snapshots of PnL
- After a week or two of running, we can analyze it by hour/day to find profitable patterns
- Each line is a snapshot of PnL at that moment
- Can aggregate by time windows (hour, day, etc.) for pattern analysis
- Much simpler than reconstructing from 200k+ trades via API

**Note**: This accumulates over time as the bot runs. Historical data from before this was implemented is not available, but going forward we'll have complete PnL history.

**Why this approach is better**:
- ✅ **No API calls** - Already receiving data via WebSocket
- ✅ **No format conversion** - Direct PnL values from exchange
- ✅ **Matches UI exactly** - Same data source as the UI uses
- ✅ **Simple** - ~15 lines of code vs complex API scripts
- ✅ **Minimal overhead** - Just append to JSONL file

---

### 📥 Querying Full Trading History via API ⚠️ (DEPRECATED - Too Complex)
**Status**: Working but not recommended

**Why deprecated**:
- Requires fetching 200k+ trades with rate limiting (slow, complex)
- Needs format conversion from API to ledger format
- Incomplete: only got partial data (-$2.28 vs UI -$36)
- Position updates approach is simpler and more accurate

**Script**: `scripts/query_api_history_v2.py`

**How it works**:
1. **Authentication**:
   - Automatically generates a fresh Bearer token using `SignerClient` each time it runs
   - Tokens expire after 1 hour, so generating fresh ensures validity
   - Falls back to `LIGHTER_API_BEARER` env var if token generation fails (may be expired)

2. **API Endpoint**: `/api/v1/trades`
   - Uses `account_index` (not `account`) in query params
   - Uses `auth` token in query params (not Authorization header)
   - Parameters: `sort_by=timestamp`, `sort_dir=desc`, `limit=100`
   - Matches the pattern used by `scripts/fetch_trades.py`

3. **Usage**:
   ```bash
   # On Railway (where API key is configured)
   railway run --service lighter-bot python3 scripts/query_api_history.py --output data/metrics/fills_api.jsonl
   ```

4. **Output**: JSONL format with all trades, can be processed by `export_pnl_windows.py` for analysis

**Why this matters**:
- Local fill ledger (`data/metrics/fills_*.jsonl`) only contains recent data
- UI PnL shows -$36 since inception, but local data only showed -$1.48
- Full API history provides complete PnL calculation matching the UI
- Enables accurate time-based analysis with full historical context

**Current Status**: ✅ **WORKING!**
- Script automatically installs `lighter-python` if needed
- Generates fresh auth token on each run (tokens expire after 1 hour)
- Fetches ALL trades via pagination (continues until fewer than `limit` trades returned)
- Successfully fetched 38,700+ trades from API
- Handles server disconnects/timeouts gracefully

**Key Implementation Details**:
1. **Token Generation**: Uses `SignerClient` directly - if not available, automatically installs via `pip install git+https://github.com/elliottech/lighter-python.git`
2. **Pagination**: Uses `offset` parameter - continues fetching until a page returns fewer than `limit` trades (indicating end of data)
3. **Error Handling**: Gracefully handles server disconnects/timeouts, exports whatever was fetched
4. **Safety Limit**: 50,000 trades max (500 pages × 100 trades) to prevent infinite loops

**Usage**:
```bash
# On Railway (automatically generates fresh token)
railway run --service lighter-bot python3 scripts/query_api_history_v2.py --output data/metrics/fills_api_complete.jsonl
```

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

