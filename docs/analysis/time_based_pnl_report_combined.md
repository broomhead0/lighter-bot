# Time-Based PnL Analysis Report

**Generated**: 2025-11-14 14:31:28

## Summary

- **Total PnL**: $-1.48
- **Total Fills**: 944
- **Total Volume**: $10,079.12
- **Average PnL per Fill**: $-0.0016

---

## 📅 By Day of Week

| Day | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|-----|-----|-------|--------|----------|------------|
| Wednesday | $-1.48 | 944 | $10,079.12 | $-0.0016 | $-0.000147 |

### Insights

- **Best Day**: Wednesday ($-0.0016 per fill)
- **Worst Day**: Wednesday ($-0.0016 per fill)

---

## 🕐 By Hour of Day (ET)

| Hour (ET) | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|-----------|-----|-------|--------|----------|------------|
| 08:00 | $-0.00 | 77 | $844.34 | $-0.0000 | $-0.000004 |
| 09:00 | $-0.57 | 245 | $2,713.56 | $-0.0023 | $-0.000211 |
| 10:00 | $-0.32 | 200 | $2,155.78 | $-0.0016 | $-0.000148 |
| 11:00 | $-0.49 | 217 | $2,301.76 | $-0.0023 | $-0.000213 |
| 12:00 | $-0.09 | 205 | $2,063.69 | $-0.0005 | $-0.000046 |

### Insights

- **Best Hour**: 08:00 ET ($-0.0000 per fill)
- **Worst Hour**: 09:00 ET ($-0.0023 per fill)

---

## ⏰ By Time Period (ET)

| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|--------|-----|-------|--------|----------|------------|
| Morning (6am-12pm ET) | $-1.38 | 739 | $8,015.43 | $-0.0019 | $-0.000173 |
| Afternoon (12pm-6pm ET) | $-0.09 | 205 | $2,063.69 | $-0.0005 | $-0.000046 |

---

## 📈 By Market Hours

| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |
|--------|-----|-------|--------|----------|------------|
| NY Market Hours (9am-4pm ET) | $-1.48 | 867 | $9,234.78 | $-0.0017 | $-0.000160 |
| Overnight (Outside NY Hours) | $-0.00 | 77 | $844.34 | $-0.0000 | $-0.000004 |

---

## 💡 Recommendations

Based on the analysis above:

1. **Identify profitable hours** - Consider increasing activity during best hours
2. **Identify losing hours** - Consider pausing or reducing size during worst hours
3. **Day-of-week patterns** - Adjust strategy based on day-specific performance
4. **Market hours** - Compare NY hours vs overnight vs weekend performance


**✅ Using True PnL Data (Profitability)**

This analysis uses `true_pnl_quote` which includes:
- **FIFO Realized PnL**: True maker edge (cost basis matched)
- **Unrealized PnL**: Inventory marked to market (inventory * (mid - cost basis))
- **Total True PnL**: Realized + Unrealized (true profitability)

This matches UI PnL and shows true profitability, not misleading cash flow.

**Note**: If this report shows negative PnL, we're losing money on inventory accumulation faster than maker fills generate profit.
