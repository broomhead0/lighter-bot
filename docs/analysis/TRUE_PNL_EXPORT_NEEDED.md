# True PnL Analysis - Export Required

## Issue

The time-based PnL analysis needs to be run with **true PnL** (profitability) instead of cash flow.

However, the local ledger file (`data/metrics/fills.jsonl`) appears to be empty or doesn't have data.

## Solution

To get true PnL analysis, you need to:

1. **Export from the live bot (Railway)**:
   ```bash
   # SSH into Railway and export with true PnL
   railway run python scripts/export_pnl_windows.py \
     --ledger data/metrics/fills.jsonl \
     --window 300 \
     --output data/analysis/pnl_5m_true.csv \
     --market-id market:2
   ```

2. **Download the CSV**:
   ```bash
   # Download from Railway
   railway run cat data/analysis/pnl_5m_true.csv > pnl_5m_true.csv
   ```

3. **Run analysis locally**:
   ```bash
   python3 scripts/analyze_time_based_pnl.py \
     --input pnl_5m_true.csv \
     --output data/analysis/time_based_pnl_analysis_true.csv \
     --report docs/analysis/time_based_pnl_report_true.md
   ```

## What Changed

The export script now calculates:
- **`fifo_realized_quote`** - True FIFO realized PnL (not cash flow)
- **`unrealized_quote`** - Unrealized PnL on inventory
- **`true_pnl_quote`** - True PnL = FIFO realized + unrealized (PROFITABILITY)

## Old vs New

**Old (cash flow)**:
- CSV sum: +$76.21 (misleading - cash flow)
- UI PnL: -$15 (true PnL including unrealized)

**New (true PnL)**:
- CSV sum: Should match UI PnL (~-$15)
- True profitability including unrealized losses

## Note

The existing CSV files (`pnl_5m.csv`, `pnl_5m_recent.csv`) are **cash flow** data, not true PnL. They show misleading positive numbers because they don't include unrealized losses on inventory.

To get accurate time-based analysis, we need to re-export from the live bot with the updated script.

