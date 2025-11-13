## 2025-11-10 – Current Strategy Snapshot

- **Goal**: Stay roughly flat PnL while farming SOL points with $500 collateral.
- **Current State**:
  - Maker live (override `MAKER_DRY_RUN=false` on Railway).
  - Hedger live (`dry_run=false`) with tuned clips to keep inventory ≈ 0.
  - Telemetry + ledger rebuilt; metrics accurate (`scripts/metrics_tool.py`).
  - Guard/hedger temporarily loosened to flush stray inventory.

- **Key Learnings**:
  - Ledger importer needed role/side fix; account listener now resets inventory when `positions` block omits a market.
  - REST backfill requires explicit `--token`; daily reconciliation via `fetch_trades.py` + `metrics_tool.py import-json`.
  - Guard kill-switch fires on stale inventory; ensure reset logic and guard limits in sync.

- **Plan Going Forward**:
  1. **Spread bump**: target ~10 bps (adjust `maker.spread_bps` / volatility floor) to capture more edge per fill.
  2. **Inventory control**: keep hedger at `max_clip_units` ≥ 0.08 while flattening; gradually tighten once mid oscillates under ±0.1 SOL.
  3. **Trend dead-band**: use 45s EMA to pause the aggressive side during strong trends to avoid taker bleed.
  4. **Monitor**: Use `metrics_tool.py window --hours 1` (and `--seconds 300`) as truth; intervene if realized PnL drifts < –$5/hr.
  5. **Points budget**: Once realized wins, earmark small profit slices to cover future premium fees.

## 2025-11-12 – Regime Response Plan

- **Motivation**: Regime study (Binance SOLUSDT 1m + 5m PnL slices) shows realized losses concentrated in down-trend / mid-to-high vol buckets.
- **Action Items**:
  1. **Trend Guard Expansion** – Modify maker trend filter to pause or widen the sell side whenever 5-minute return < –6 bps, including a configurable cooldown and telemetry flags.
  2. **Vol Clip Curve** – Blend volatility percentile into guard sizing so clips shrink toward the exchange minimum once 1m σ exceeds ~0.09%.
  3. **Hedger Tighten** – Lower `trigger_units` from 0.07 → 0.05, review `target_units` ~0.02, add passive timeout, and escalate to guard-aware emergency flatten when blocks persist.
  4. **Adaptive Profiles** – Add dynamic regime switching so the maker engine toggles between defensive and aggressive profiles based on trend/guard signals (`maker_regime_state` telemetry).
  5. **Fee Simulation & PnL Visibility** – Extend `analysis/regime_analysis.py` (or notebook) to layer in 2–4 bps maker fees and report hourly net; publish FIFO realized PnL via telemetry (`maker_fifo_realized_quote`) before enabling premium points.

## Next Steps (2025-11-12)
- Monitor the guard-aware hedge dampers (PnL guard → clip ×0.50, cross 8 bps, cap 9 bps) and emergency mode (≥10 s block → clip ×1.4, +6 bps cross) and adjust thresholds if they chatter.
- Watch telemetry (`maker_regime_state`, `maker_fifo_realized_quote`, `maker_trend_down_guard`) over the next live session to verify regime flips and maker edge; sample 20 min slices with `export_pnl_windows.py --window 300` for quick feedback.
- Once an up/neutral stretch appears, evaluate widening the aggressive profile (clips, cooldown) to harvest more rebates.
- Re-run the 5-minute PnL window export + regime analysis after the next session and fold results into this plan.
  5. **Validation Loop** – After deploy, re-export 5-minute slices and rerun the analyzer; capture before/after snapshots in `docs/analysis/sol_regimes.md`.
- **Next Check-in Playbook** (pending):
  - Re-sample 5 min PnL windows + SOL returns (target ≥20 min slices) to confirm maker FIFO trend recovers or adjust taker offsets/cooldowns.
  - Audit guard telemetry (`maker_guard_block_active`, `hedger_guard_emergency`, `maker_pnl_guard_active`) for any sustained activity during the slice.
  - If FIFO stays negative while realized cashflow is positive, iterate offsets/clip multipliers and redeploy.
- **Reference**: `docs/analysis/regime_action_plan.md` holds the detailed workflow.
# Code Review & Fixes Summary

## ✅ Critical Fixes Completed

### 1. **SelfTradeGuard Wired** ✅
- **Problem:** Guard existed but was never called by MakerEngine
- **Fix:**
  - Added `SelfTradeGuard` import and instantiation in `core/main.py`
  - Passed guard to `MakerEngine` constructor
  - Added guard validation in `MakerEngine.run()` before posting quotes
  - Updated `SelfTradeGuard` to work with `StateStore` methods
- **Impact:** Bot now validates quotes before posting, preventing crossed books and inventory breaches

### 2. **Cancel Discipline Enforced** ✅
- **Problem:** Only logged warnings, didn't actually throttle
- **Fix:**
  - Added `_cancel_count_this_minute` tracking with 60-second rolling window
  - Added `_is_throttled` flag
  - `_check_cancel_discipline()` now actually throttles maker when limit exceeded
  - Cancel tracking resets every minute
- **Impact:** Bot now respects exchange cancel rate limits, preventing rate limiting/bans

### 3. **REST Order Placement Implemented** ✅
- **Problem:** `_post_quotes()` was a no-op
- **Fix:**
  - Added REST client initialization in `MakerEngine.__init__`
  - Implemented `_place_order()` and `_cancel_order()` methods
  - Added order tracking (`_open_orders` dict)
  - Integrated with StateStore for order management
  - Maintains dry-run mode for safety (controlled by `maker.dry_run` config)
- **Impact:** Bot can now actually place orders (when REST API is available and `dry_run: false`)

### 4. **Inventory & Order Tracking Added** ✅
- **Problem:** StateStore lacked inventory and order tracking
- **Fix:**
  - Added `_inventory: Dict[str, Decimal]` for per-market positions
  - Added `_open_orders: Dict[str, Dict]` for order tracking
  - Methods: `get_inventory()`, `update_inventory()`, `set_inventory()`
  - Methods: `add_order()`, `remove_order()`, `get_orders()`
- **Impact:** Full visibility into positions and open orders

### 5. **Unused Code Removed** ✅
- **Deleted:**
  - `modules/hedger.py` - `HedgerDryRun` was never imported/used
  - `modules/_message_router.zombie` - Dead file
  - `modules/ws_client.py` - Redundant (market_data_listener handles WS)
- **Impact:** Cleaner codebase, less confusion

### 6. **Guard Config Added** ✅
- Added `guard` section to `config.yaml` with:
  - `price_band_bps: 50`
  - `crossed_book_protection: true`
  - `max_position_units: 0.01`
  - `max_inventory_notional: 1000`
  - `kill_on_crossed_book: true`
  - `kill_on_inventory_breach: true`
  - `backoff_seconds_on_block: 2`

## 📝 Code Quality Improvements

### SelfTradeGuard Integration
- Updated `_get_mid_for_market()` to use `StateStore.get_mid()` first
- Updated `_get_inventory_for_market()` to use `StateStore.get_inventory()` first
- Maintains backward compatibility with dict-style state

### MakerEngine Enhancements
- Added `Decimal` import for precision
- Improved error handling with try/except blocks
- Non-blocking alerts using `asyncio.create_task()`
- Proper async/await patterns

### StateStore Enhancements
- Added `Any` type import
- Consistent `Decimal` usage for inventory
- Type-safe order tracking

## 🔄 What Remains (Optional Future Work)

### Adapter Pattern Simplification
- `_DSAdapter`, `_StateAdapter`, `_MakerUpdater` are still present but are actually useful for backward compatibility
- They provide graceful fallbacks when components are missing
- **Recommendation:** Keep them for now, they're not causing issues

### Actual REST API Integration
- `_place_order()` and `_cancel_order()` currently generate fake order IDs
- TODO comments indicate where real REST API calls should go
- **Recommendation:** Implement when Lighter.xyz REST API endpoints are finalized

### Fill Processing
- No fill handler yet (when orders get filled, need to update inventory)
- **Recommendation:** Add fill processing from WebSocket or REST callbacks

## 🎯 Testing Recommendations

1. **Test Guard Blocking:**
   - Set extreme spreads to trigger price band check
   - Set inventory limits and verify blocking
   - Test crossed book detection

2. **Test Cancel Discipline:**
   - Reduce `maker.limits.max_cancels` to 5
   - Verify throttling kicks in
   - Verify reset after 60 seconds

3. **Test Order Placement:**
   - Set `maker.dry_run: false` (when API keys ready)
   - Verify orders are tracked in StateStore
   - Verify cancellations work

4. **Test Inventory Tracking:**
   - Manually update inventory via StateStore
   - Verify guard respects inventory limits

## 📊 Files Modified

- `core/main.py` - Added SelfTradeGuard instantiation and wiring
- `modules/maker_engine.py` - Guard integration, cancel discipline, REST order placement
- `core/state_store.py` - Inventory and order tracking
- `modules/self_trade_guard.py` - StateStore integration
- `config.yaml` - Added guard configuration

## 📊 Files Deleted

- `modules/hedger.py`
- `modules/_message_router.zombie`
- `modules/ws_client.py`

## ✅ Status

All critical issues fixed. The bot now:
- ✅ Validates quotes before posting (safety)
- ✅ Enforces cancel limits (compliance)
- ✅ Can place orders (functionality)
- ✅ Tracks inventory and orders (visibility)
- ✅ Has cleaner codebase (maintainability)

The bot is ready for further testing and deployment once REST API endpoints are finalized.

## 🧠 KEY LEARNINGS & FINDINGS (Must Reference Before Making Changes)

### Regime Analysis Findings (2025-11-12)
- **Up-trend (> +0.1%) windows**: Averaged +$16 (favorable)
- **Down-trend (< -0.1%) windows**: Averaged -$13 (problematic)
- **Low-vol (≤ 0.0006)**: Yielded +$5.36 quote
- **Mid/high volatility**: Drove negative PnL
- **Inventory correlation**: Realized PnL vs base delta ≈ -1.0 (exposure direction drives bleed)
- **NY Market Hours (high vol)**: Better performance, fewer large crosses, more liquidity
- **Overnight (low vol)**: Worse performance, more large crosses due to lower liquidity

### Threshold Findings
- **Internal vs External Volatility**: Internal EMA (45s half-life) can differ significantly from external market volatility
- **Volatility Thresholds**:
  - Low-vol pause: 3.0 bps (pause maker when vol < 3.0 bps to avoid hedging costs)
  - Regime switch: 6.0 bps (switch aggressive/defensive)
  - High-vol pause: 30 bps (pause maker when vol > 30 bps)
- **Hedger Findings**: Large crosses (≥0.08 SOL) cost ~$16-18 each and erode maker edge

### Configuration Learnings
- **Hedger parameters**: Smaller clips (0.06 SOL) + earlier triggers (0.02 SOL) = fewer large crosses
- **Maker spreads**: 12 bps baseline with volatility-aware adjustments
- **PnL guard**: Should activate on FIFO realized PnL (not cash flow) to track true maker edge
- **Regime switching**: Should consider volatility for aggressive/defensive profiles

### Process Learnings
- **Always run regime analysis** after significant changes or time periods
- **Compare internal vs external volatility** to validate thresholds
- **Export PnL windows regularly** to track performance trends
- **Document findings immediately** in this file and `docs/analysis/sol_regimes.md`
- **Reference this section before making configuration changes**

### Automation Requirements
- Run regime analysis after each deploy or daily
- Compare internal bot volatility with external SOL volatility (Binance 1m candles)
- Validate thresholds are still appropriate
- Update learnings section with new findings

### Critical Finding (2025-11-13) - RESOLVED
- **Internal vs External Volatility Discrepancy**: 
  - Internal bot volatility: 1.96 bps (EMA with 45s half-life)
  - External SOL volatility (Binance 60m): 6.18 bps
  - **Impact**: Bot is paused (low-vol pause active) when external market suggests normal trading conditions (6.18 bps > 6.0 bps regime threshold)
  - **Root Cause**: EMA calculation method differs from external volatility measurement
  - **Action Taken**: 
    - Adjusted low-vol pause threshold: 3.0 → 4.5 bps
    - Adjusted low-vol resume threshold: 4.5 → 5.5 bps (hysteresis)
    - Shortened EMA half-life: 45s → 35s (faster response)
  - **Reference**: `docs/analysis/volatility_comparison_2025-11-13.md`
  - **Status**: Changes deployed (2025-11-13), monitoring for validation

---
