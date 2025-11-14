# PnL Calculation Issue - November 15, 2025

## Problem

The export script calculates true PnL, but the results don't match UI PnL:
- **Export script**: -$1.43 (from full dataset)
- **UI PnL**: **-$36** (actual since inception)
- **Difference**: $34.57

## Root Causes

### 1. Incomplete Data
The local ledger files are **subsets** of full history:
- `fills_recent.jsonl`: 422 events (recent only)
- `fills_remote.jsonl`: 522 events (partial)
- **Missing**: Most trading history since inception

**Impact**: Can't calculate true PnL from incomplete data.

### 2. Possible Calculation Errors
Even with full data, the calculation might be wrong:
- **FIFO Realized PnL**: Might not match UI's calculation
- **Unrealized PnL**: Cost basis tracking might be incorrect
- **Inventory tracking**: Might not match exchange positions

## Solutions

### Option 1: Export Full Ledger from Railway ✅ (Recommended)
```bash
# SSH into Railway and export ALL history
railway run python scripts/export_pnl_windows.py \
  --ledger data/metrics/fills.jsonl \
  --window 300 \
  --output data/analysis/pnl_5m_full_history.csv \
  --market-id market:2

# Download the full export
railway run cat data/analysis/pnl_5m_full_history.csv > pnl_5m_full_history.csv
```

### Option 2: Use UI PnL Directly
Instead of calculating from fills, use the UI's PnL calculation which is the source of truth.

### Option 3: Fix Calculation Algorithm
Review and fix the FIFO realized and unrealized PnL calculations to match UI exactly.

## Current Status

**Analysis is using incomplete data** - results don't match UI PnL of -$36.

**Recommendation**: Export full ledger from Railway before doing time-based analysis.

## Notes

- The export script now calculates `true_pnl_quote` (profitability, not cash flow) ✅
- The analysis script now handles cumulative values correctly (deltas) ✅
- But we're using incomplete data, so results are wrong ❌

---

**Next Steps**: Export full ledger from Railway and re-run analysis.

