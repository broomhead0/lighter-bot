# Regime Analysis Checklist

**Purpose:** Ensure we regularly validate bot performance against market conditions and remember key findings.

## ✅ Before Making Configuration Changes

1. **Read CHANGES_SUMMARY.md** - Review "KEY LEARNINGS & FINDINGS" section
2. **Check recent findings** - Review latest analysis in `docs/analysis/`
3. **Understand context** - Don't repeat past mistakes or ignore previous findings

## 📊 Regular Analysis (After Each Deploy or Daily)

### 1. Quick Volatility Check (5 minutes)
```bash
python scripts/regime_check.py
```
- Compares internal bot volatility vs external SOL volatility (Binance)
- Validates thresholds are still appropriate
- Flags discrepancies for investigation

### 2. Export PnL Windows (2 minutes)
```bash
railway ssh --service lighter-bot -- python scripts/export_pnl_windows.py \
  --ledger data/metrics/fills.jsonl \
  --window 300 \
  --output /tmp/pnl_5m_recent.csv
```

### 3. Fetch Market Data (if needed)
```bash
python scripts/regime_check.py  # Fetches Binance candles automatically
```

### 4. Run Full Regime Analysis (10 minutes)
```bash
PYTHONPATH=. python analysis/regime_analysis.py \
  --pnl-csv /tmp/pnl_5m_recent.csv \
  --candles-json data/analysis/binance_solusdt_1m_recent.json
```

### 5. Document Findings (5 minutes)
- Update `CHANGES_SUMMARY.md` with new learnings
- Add findings to `docs/analysis/sol_regimes.md`
- Create new analysis doc if significant findings

## 🔍 What to Look For

### Volatility Discrepancies
- Internal bot volatility vs external market volatility
- If > 2x difference, investigate why
- Consider adjusting thresholds if consistently different

### Performance Patterns
- How does bot perform in different volatility regimes?
- Up-trend vs down-trend performance
- NY market hours vs overnight performance
- High volatility vs low volatility performance

### Threshold Validation
- Are current thresholds (3.0 bps pause, 6.0 bps regime switch) appropriate?
- Should they be adjusted based on findings?
- Are we being too conservative or too aggressive?

### Hedger Performance
- Large crosses frequency and cost
- Impact on realized PnL
- Inventory buildup patterns

## 📝 Documentation Requirements

1. **Immediate**: Document any significant findings in `CHANGES_SUMMARY.md`
2. **Detailed**: Add analysis results to `docs/analysis/sol_regimes.md`
3. **Actionable**: If thresholds need adjustment, update both code and documentation

## ⚠️ Red Flags

Watch for these and investigate immediately:
- Internal volatility < 3.0 bps but external > 6.0 bps (current issue)
- Consistent negative FIFO realized PnL
- Frequent large crosses (>10 per hour)
- Inventory buildup > 0.05 SOL
- PnL guard active for > 30 minutes continuously

## 🔄 Process

1. **After deploy**: Run quick volatility check within 1 hour
2. **Daily**: Run full analysis if bot has been active
3. **Weekly**: Review all findings and validate thresholds
4. **Before changes**: Always check learnings section first

## 📚 Reference Documents

- `CHANGES_SUMMARY.md` - Key learnings and findings
- `docs/analysis/sol_regimes.md` - Regime analysis workflow and findings
- `docs/analysis/regime_action_plan.md` - Action plan from findings
- `docs/analysis/volatility_comparison_*.md` - Specific volatility comparisons

