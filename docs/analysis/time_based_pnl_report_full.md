# Time-Based PnL Analysis Report

**Generated**: 2025-11-14 13:53:31

## Summary

- **Total PnL**: $76.21
- **Total Fills**: 2,569
- **Total Volume**: $28,581.34
- **Average PnL per Fill**: $0.0297

---

## 📅 By Day of Week

| Day | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|-----|-----|-------|--------|----------|------------|
| Tuesday | $47.33 | 2,165 | $24,194.79 | $0.0219 | $0.001956 |
| Wednesday | $28.88 | 404 | $4,386.55 | $0.0715 | $0.006583 |

### Insights

- **Best Day**: Wednesday ($0.0715 per fill)
- **Worst Day**: Tuesday ($0.0219 per fill)

---

## 🕐 By Hour of Day (ET)

| Hour (ET) | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|-----------|-----|-------|--------|----------|------------|
| 10:00 | $12.05 | 213 | $2,475.33 | $0.0566 | $0.004869 |
| 11:00 | $-20.87 | 323 | $3,690.93 | $-0.0646 | $-0.005655 |
| 12:00 | $8.20 | 202 | $2,309.88 | $0.0406 | $0.003548 |
| 13:00 | $-9.53 | 228 | $2,619.87 | $-0.0418 | $-0.003639 |
| 14:00 | $109.23 | 195 | $2,265.40 | $0.5602 | $0.048217 |
| 15:00 | $-108.25 | 239 | $2,622.87 | $-0.4529 | $-0.041273 |
| 16:00 | $-3.13 | 277 | $3,002.37 | $-0.0113 | $-0.001042 |
| 17:00 | $4.00 | 199 | $2,153.85 | $0.0201 | $0.001857 |
| 18:00 | $55.64 | 289 | $3,054.29 | $0.1925 | $0.018217 |
| 19:00 | $-72.22 | 380 | $4,099.96 | $-0.1901 | $-0.017615 |
| 20:00 | $101.10 | 24 | $286.58 | $4.2125 | $0.352774 |

### Insights

- **Best Hour**: 20:00 ET ($4.2125 per fill)
- **Worst Hour**: 15:00 ET ($-0.4529 per fill)

---

## ⏰ By Time Period (ET)

| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|--------|-----|-------|--------|----------|------------|
| Morning (6am-12pm ET) | $-8.82 | 536 | $6,166.26 | $-0.0165 | $-0.001431 |
| Afternoon (12pm-6pm ET) | $0.51 | 1,340 | $14,974.25 | $0.0004 | $0.000034 |
| Evening (6pm-12am ET) | $84.52 | 693 | $7,440.83 | $0.1220 | $0.011359 |

---

## 📈 By Market Hours

| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|--------|-----|-------|--------|----------|------------|
| NY Market Hours (9am-4pm ET) | $-9.18 | 1,400 | $15,984.28 | $-0.0066 | $-0.000574 |
| Overnight (Outside NY Hours) | $85.39 | 1,169 | $12,597.05 | $0.0730 | $0.006779 |

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
