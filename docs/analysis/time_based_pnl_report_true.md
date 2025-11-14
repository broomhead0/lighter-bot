# Time-Based PnL Analysis Report

**Generated**: 2025-11-14 14:14:40

## Summary

- **Total PnL**: $-157.81
- **Total Fills**: 422
- **Total Volume**: $4,365.45
- **Average PnL per Fill**: $-0.3740

---

## 📅 By Day of Week

| Day | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|-----|-----|-------|--------|----------|------------|
| Wednesday | $-157.81 | 422 | $4,365.45 | $-0.3740 | $-0.036150 |

### Insights

- **Best Day**: Wednesday ($-0.3740 per fill)
- **Worst Day**: Wednesday ($-0.3740 per fill)

---

## 🕐 By Hour of Day (ET)

| Hour (ET) | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|-----------|-----|-------|--------|----------|------------|
| 11:00 | $-120.16 | 217 | $2,301.76 | $-0.5537 | $-0.052203 |
| 12:00 | $-37.65 | 205 | $2,063.69 | $-0.1837 | $-0.018245 |

### Insights

- **Best Hour**: 12:00 ET ($-0.1837 per fill)
- **Worst Hour**: 11:00 ET ($-0.5537 per fill)

---

## ⏰ By Time Period (ET)

| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|--------|-----|-------|--------|----------|------------|
| Morning (6am-12pm ET) | $-120.16 | 217 | $2,301.76 | $-0.5537 | $-0.052203 |
| Afternoon (12pm-6pm ET) | $-37.65 | 205 | $2,063.69 | $-0.1837 | $-0.018245 |

---

## 📈 By Market Hours

| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|--------|-----|-------|--------|----------|------------|
| NY Market Hours (9am-4pm ET) | $-157.81 | 422 | $4,365.45 | $-0.3740 | $-0.036150 |

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
- CSV sum: +$76.21 (cash flow)
- UI PnL: -$15 (true PnL including unrealized losses)
- We're losing money on inventory accumulation!

**For true PnL**, monitor UI PnL or telemetry's `maker_fifo_realized_quote`.
