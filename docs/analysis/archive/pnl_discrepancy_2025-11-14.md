# PnL Discrepancy Analysis - November 14, 2025

## Problem Statement

**User UI shows: -$13 since 11/10** (actual loss)
**CSV metrics show: +$9.27** (misleading - cash flow only)
**Discrepancy: ~$22 difference**

## Root Cause

### CSV "realized_quote" is NOT true PnL

The CSV export (`scripts/export_pnl_windows.py`) calculates:
```python
entry["realized_quote"] += numbers["quote_delta"] - numbers["fee_paid"]
```

This is **CASH FLOW**, not true realized PnL. It does NOT account for:
1. **Unrealized PnL** on open positions (inventory held)
2. **True FIFO realized PnL** (proper cost basis matching)
3. **Mark-to-market** on open positions

### Why the Discrepancy?

**CSV shows: +$9.27** (cash in - cash out)
- Positive cash flow from maker fills
- But doesn't account for inventory losses

**UI shows: -$13** (actual PnL)
- Cash flow: +$9.27
- **Unrealized PnL on inventory: ~-$22**
- **Total: -$13** ✓

## What This Means

### The Bot is Losing Money
- **Cash flow**: Slightly positive (+$9.27)
- **True PnL**: Negative (-$13) due to inventory losses
- **Root cause**: Inventory buildup causing unrealized losses

### The Real Problem
1. **Inventory accumulating** - We're holding positions that lose value
2. **Maker fills** are generating cash flow (+$9.27)
3. **But inventory losses** are eating into that (-$22)
4. **Net result**: -$13 loss

## What We Need to Track

### Correct Metrics (from CHANGES_SUMMARY.md):
- **`maker_fifo_realized_quote`** - FIFO realized PnL (true maker edge)
- **`metrics_total_unrealized`** - Unrealized PnL on open positions
- **`metrics_total_pnl`** - Total PnL (realized + unrealized)

### CSV Export Needs Fix
The `export_pnl_windows.py` should export:
- FIFO realized PnL (not cash flow)
- Unrealized PnL per window
- Total PnL (realized + unrealized)

## Immediate Actions

1. **Stop using CSV "realized_quote" for PnL analysis** - It's misleading
2. **Check telemetry for FIFO realized PnL** - `maker_fifo_realized_quote`
3. **Check unrealized PnL** - `metrics_total_unrealized`
4. **Compare UI PnL vs metrics** - Verify they align

## Why This Matters

The user correctly identified that we've lost $13 since 11/10. Our CSV analysis was wrong because:
- We looked at cash flow (+$9.27)
- Missed unrealized losses on inventory (-$22)
- Didn't understand the full picture

**The bot needs to:**
1. **Flatten inventory faster** (hedger fix should help)
2. **Prevent inventory buildup** (asymmetric quoting should help)
3. **Track true PnL** (FIFO + unrealized, not just cash flow)

## Next Steps

1. ✅ Acknowledge the discrepancy (DONE)
2. ⏳ Check FIFO realized PnL from telemetry
3. ⏳ Check unrealized PnL from telemetry
4. ⏳ Fix CSV export to include unrealized PnL
5. ⏳ Re-do regime analysis with correct PnL data
6. ⏳ Compare to UI PnL to validate metrics

