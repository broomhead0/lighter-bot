# Codebase Cleanup Audit - November 15, 2025

**Purpose**: Identify unused code, docs, and config that can be deleted/deprecated to reduce maintenance burden and context loss.

---

## ✅ Items to DELETE (Definitely Unused)

### 1. **`garmin_to_csv.py`** (Root Directory)
- **Status**: Completely unrelated to trading bot
- **Purpose**: Appears to be for Garmin fitness device data conversion
- **Action**: ✅ DELETE - No relationship to bot functionality

### 2. **`core/config.py`** (Unused Config Module)
- **Status**: Defined but never imported/used
- **Evidence**: `main.py` loads YAML directly with `yaml.safe_load()`, doesn't import `core.config`
- **Action**: ✅ DELETE - Redundant, main.py handles config loading directly

### 3. **`modules/pair_selector.py`** (If It Exists)
- **Status**: Referenced in `main.py` import but file doesn't exist
- **Evidence**: `main.py` line 24-26 tries to import `PairSelector` but it's not found in modules/
- **Action**: ✅ REMOVE IMPORT - Import already handles exception, just remove the try/except block

### 4. **`config.yaml.backup.20251105_133114`** (Old Backup)
- **Status**: Backup file from November 5
- **Action**: ✅ DELETE - Old backup, not needed

---

## ⚠️ Items to DEPRECATE (Disabled in Config)

### 1. **Funding Optimizer** (`modules/funding_optimizer.py`)
- **Config**: `optimizer.enabled: false` (line 143)
- **Status**: Code exists and is imported, but disabled in config
- **Recommendation**: Keep for now (can be enabled easily), but mark as optional/experimental
- **Action**: ⚠️ DEPRECATE DOCUMENTATION - Update README/docs to note it's experimental

### 2. **Mean Reversion Trader** (`modules/mean_reversion_trader.py`)
- **Config**: `mean_reversion.enabled: false` (line 207)
- **Status**: Code exists and is imported, but disabled in config
- **Recommendation**: Keep for now (can be enabled easily), but mark as optional/experimental
- **Action**: ⚠️ DEPRECATE DOCUMENTATION - Update README/docs to note it's experimental

### 3. **Chaos Injector** (`modules/chaos_injector.py`)
- **Config**: `chaos.enabled: false` (line 148) (but sub-features enabled)
- **Status**: Used for testing, some sub-features enabled
- **Recommendation**: Keep (useful for testing), but note it's for testing only
- **Action**: ⚠️ DOCUMENT - Already documented in CHAOS_TESTING.md, keep

### 4. **Replay Mode** (`scripts/replay_sim.py`, `scripts/replay.py`)
- **Config**: `replay.enabled: false` (line 157)
- **Status**: Testing/debugging tool
- **Recommendation**: Keep (useful for testing/debugging)
- **Action**: ⚠️ DOCUMENT - Already documented in TESTING_REPLAY.md, keep

---

## 📚 Docs That Can Be Consolidated/Archived

### Superseded by MASTER_DOC.md:
- ✅ **KEEP**: `docs/MASTER_DOC.md` - Single source of truth (created today)
- ⚠️ **ARCHIVE**: Most analysis docs in `docs/analysis/` - Historical snapshots, reference only
- ⚠️ **ARCHIVE**: `CHANGES_SUMMARY.md` - Historical, can reference but don't update
- ⚠️ **ARCHIVE**: `CODE_REVIEW.md` - Historical, outdated references

### Still Useful (Keep):
- ✅ `docs/CONFIG_STRATEGY.md` - Current strategy
- ✅ `docs/CONFIG_AUDIT.md` - Useful audit reference
- ✅ `docs/MASTER_DOC.md` - Primary reference
- ✅ `README.md` - Entry point
- ✅ `CHAOS_TESTING.md` - Testing docs
- ✅ `TESTING_REPLAY.md` - Testing docs
- ✅ `DEPLOYMENT.md` - Deployment guide

### Could Be Consolidated:
- ⚠️ Multiple deployment docs (`DEPLOYMENT.md`, `DEPLOYMENT_STEPS.md`, `DEPLOY_QUICKSTART.md`, `PRE_DEPLOYMENT.md`)
- ⚠️ Multiple monitoring docs (`MONITORING_GUIDE.md`, `MONITORING_SETUP.md`)
- ⚠️ Multiple Docker docs (`DOCKER.md`, `DOCKER_SETUP.md`, `DOCKER_START.md`)

**Recommendation**: Consolidate deployment, monitoring, and Docker docs into single comprehensive guides.

---

## 🧪 Test Scripts (Keep vs Delete)

### Keep (Still Useful):
- ✅ `scripts/export_pnl_windows.py` - Used for analysis
- ✅ `scripts/fetch_candles.py` - Used for analysis
- ✅ `scripts/dump_metrics.py` - Used for monitoring
- ✅ `scripts/metrics_tool.py` - Used for metrics management
- ✅ `scripts/test_chaos.py` - Testing tool
- ✅ `scripts/test_replay_interactive.py` - Testing tool

### Potentially Remove:
- ⚠️ `scripts/test_cancel_discipline.py` - One-time test, probably no longer needed
- ⚠️ `scripts/test_critical_fixes.py` - One-time test, probably no longer needed
- ⚠️ `scripts/generate_test_replay_data.py` - Only needed when creating test data

**Recommendation**: Keep test scripts for now, but archive old one-time tests.

---

## 📁 Data Files (Review)

### Analysis Data:
- `data/analysis/*.json` - Historical analysis data
- `data/analysis/*.csv` - Historical PnL exports

**Recommendation**: Keep recent data, archive or delete very old files (>1 month old)

### Metrics Data:
- `data/metrics/fills*.jsonl` - Active metrics
- `data/metrics/archive/` - Archived metrics

**Recommendation**: Keep (actively used)

---

## 🔧 Code Cleanup Recommendations

### 1. Remove Unused Import in `main.py`
```python
# Remove this block (lines 23-26):
try:
    from modules.pair_selector import PairSelector
except Exception:  # noqa
    PairSelector = None  # type: ignore
```
**Reason**: Module doesn't exist, import always fails

### 2. Simplify `_try_construct` Usage
- Current: 6+ variants per component
- Recommendation: Standardize on one signature or use proper dependency injection
- **Action**: ⚠️ LOW PRIORITY - Works but could be cleaner

### 3. Consolidate Adapter Classes
- `_DSAdapter`, `_StateAdapter`, `_MakerUpdater` add complexity
- **Action**: ⚠️ LOW PRIORITY - Consider simplifying if optimizer is not used

---

## ✅ Recommended Actions (Priority Order)

### HIGH PRIORITY (Do Now):
1. ✅ **DELETE** `garmin_to_csv.py` - Completely unrelated
2. ✅ **DELETE** `core/config.py` - Unused module
3. ✅ **DELETE** `config.yaml.backup.20251105_133114` - Old backup
4. ✅ **REMOVE** unused `PairSelector` import from `main.py`

### MEDIUM PRIORITY (Do Soon):
5. ⚠️ **ARCHIVE** old analysis docs to `docs/analysis/archive/`
6. ⚠️ **CONSOLIDATE** deployment docs (3 docs → 1)
7. ⚠️ **CONSOLIDATE** monitoring docs (2 docs → 1)
8. ⚠️ **CONSOLIDATE** Docker docs (3 docs → 1)

### LOW PRIORITY (Future):
9. ⚠️ **REVIEW** test scripts - archive old one-time tests
10. ⚠️ **CLEANUP** data files - archive/delete old analysis data
11. ⚠️ **SIMPLIFY** adapter pattern if optimizer stays disabled
12. ⚠️ **STANDARDIZE** constructor patterns

---

## 📝 Notes

### Why Keep Disabled Features:
- **Optimizer**: Can be enabled for multi-market trading
- **Mean Reversion**: Alternative trading strategy
- **Chaos/Replay**: Useful for testing and debugging
- **Recommendation**: Keep code, but document as optional/experimental

### Why Archive vs Delete:
- **Archive**: Keep for reference, but don't update
- **Delete**: Completely remove if never needed
- **Deprecate**: Mark as optional/experimental, may remove later

---

## 🎯 Summary

**Files to DELETE (4)**:
1. `garmin_to_csv.py`
2. `core/config.py`
3. `config.yaml.backup.20251105_133114`
4. Remove `PairSelector` import from `main.py`

**Docs to CONSOLIDATE (8 docs → 3 docs)**:
- Deployment: 3 → 1
- Monitoring: 2 → 1
- Docker: 3 → 1

**Code to CLEANUP (Low Priority)**:
- Simplify adapters if optimizer unused
- Standardize constructors

**Result**: Cleaner codebase, easier maintenance, less context loss

