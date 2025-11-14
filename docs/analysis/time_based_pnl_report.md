# Time-Based PnL Analysis Report

**Generated**: 2025-11-14 13:53:26

## Summary

- **Total PnL**: $9.27
- **Total Fills**: 634
- **Total Volume**: $3,166.83
- **Average PnL per Fill**: $0.0146

---

## 📅 By Day of Week

| Day | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|-----|-----|-------|--------|----------|------------|
| Friday | $9.27 | 634 | $3,166.83 | $0.0146 | $0.002928 |

### Insights

- **Best Day**: Friday ($0.0146 per fill)
- **Worst Day**: Friday ($0.0146 per fill)

---

## 🕐 By Hour of Day (ET)

| Hour (ET) | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|-----------|-----|-------|--------|----------|------------|
| 22:00 | $3.14 | 146 | $723.14 | $0.0215 | $0.004347 |
| 23:00 | $6.13 | 488 | $2,443.69 | $0.0126 | $0.002508 |

### Insights

- **Best Hour**: 22:00 ET ($0.0215 per fill)
- **Worst Hour**: 23:00 ET ($0.0126 per fill)

---

## ⏰ By Time Period (ET)

| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|--------|-----|-------|--------|----------|------------|
| Evening (6pm-12am ET) | $9.27 | 634 | $3,166.83 | $0.0146 | $0.002928 |

---

## 📈 By Market Hours

| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|--------|-----|-------|--------|----------|------------|
| Overnight (Outside NY Hours) | $9.27 | 634 | $3,166.83 | $0.0146 | $0.002928 |

---

## 💡 Recommendations

Based on the analysis above:

1. **Identify profitable hours** - Consider increasing activity during best hours
2. **Identify losing hours** - Consider pausing or reducing size during worst hours
3. **Day-of-week patterns** - Adjust strategy based on day-specific performance
4. **Market hours** - Compare NY hours vs overnight vs weekend performance

**⚠️ CRITICAL WARNING**: This analysis uses `realized_quote` which is **CASH FLOW**, not true PnL!

**What it measures**: Cash flow from fills (quote_delta - fees)  
**What it DOES NOT measure**: Unrealized losses on inventory, true FIFO realized PnL

**Example**: 
- We buy 0.1 SOL at $100 = +$10 cash flow (shows in CSV)
- Price drops to $90, we still hold it
- CSV shows: +$10 (cash flow)
- True PnL: -$1 (unrealized loss not captured in CSV)

**This is why**:
- CSV sum: +$9.27 (cash flow from this session)
- UI PnL: -$15+ (true PnL including unrealized losses)
- We're losing money on inventory accumulation!

**For true PnL**, monitor UI PnL or telemetry's `maker_fifo_realized_quote`.
