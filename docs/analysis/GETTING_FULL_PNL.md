# Getting Full PnL History - Solution

## The Problem

Export script shows -$1.48 (from 944 fills) but UI PnL is -$36 since inception.

## The Root Cause

Our local ledger files only contain **recent fills** (944 total), not the full history since inception.

## The Solution

The exchange provides `realized_pnl` in position updates via WebSocket - **this is the source of truth!**

### Option 1: Track Position Updates Going Forward ✅ (Best Long-term)

Modify `account_listener.py` to log position updates (including `realized_pnl`) to a separate ledger:

```python
# In account_listener.py _handle_position_entry:
if entry.get("realized_pnl") is not None:
    # Log position update with realized_pnl
    # This matches UI PnL exactly!
    position_ledger.append({
        "timestamp": time.time(),
        "market": market,
        "realized_pnl": entry.get("realized_pnl"),
        "unrealized_pnl": entry.get("unrealized_pnl"),
        "total_pnl": float(entry.get("realized_pnl", 0)) + float(entry.get("unrealized_pnl", 0)),
        "position": entry.get("position"),
    })
```

**Benefits:**
- Matches UI PnL exactly (same source)
- No calculation needed
- Includes all adjustments (funding, etc.)

### Option 2: Query Exchange API for Current Position

The exchange REST API might provide current position info including `realized_pnl`. Check:
- `/api/v1/account/{account_id}/position`
- `/api/v1/account/{account_id}` 
- Or check SignerClient methods in `lighter-python` SDK

**Limitation:** Only gives current snapshot, not historical.

### Option 3: Parse Railway Logs (Historical)

Extract position updates from Railway logs:

```bash
railway logs --service lighter-bot --since 7d | \
  grep -o '"realized_pnl":"[^"]*"' | \
  python3 parse_position_updates.py
```

**Limitation:** Logs might not have full history (rotated/deleted).

## Recommended Approach

**Start tracking position updates going forward** (Option 1):

1. Modify `account_listener.py` to log position updates to `data/metrics/positions.jsonl`
2. Export position snapshots for time-based analysis
3. Use `realized_pnl + unrealized_pnl` directly from exchange (matches UI!)

This ensures future analysis matches UI PnL exactly.

---

## Current Status

- ✅ FIFO calculation fixed (processes ALL fills, not just maker)
- ❌ Still missing historical fills (only 944 vs full history)
- ✅ Exchange provides `realized_pnl` in position updates (source of truth)
- ⏳ Need to track position updates going forward

