## Regime Response Plan (2025-11-12)

**Objective:** Turn the regime study into concrete maker/hedger changes that push realized PnL back to neutral/positive before enabling premium fees.

### 1. Trend-Gated Quoting
- Gate or widen the “danger side” whenever 5-minute price return is below –6 bps, and pause bid quoting for `down_cooldown_seconds` (45 s) after a trigger.
- Leverage existing `maker.trend` block: add a configurable downside threshold, extra spread additive, and cooldown telemetry.
- Telemetry: expose gauges for downtrend guard and cooldown status (`maker_trend_down_guard`, `maker_trend_down_cooldown_active`).

### 2. Volatility-Aware Clip Scaling
- Use minute-level realized vol from `MakerEngine._latest_volatility_bps`.
- Introduce a second size curve: shrink clips toward exchange minimum as vol crosses the 75th percentile (~0.0009) and pause sizing increases until vol relents.
- Maintain compatibility with guard scaling and lot quantisation.

### 3. Hedger Tightening
- Revisit `hedger.trigger_units` and `target_units` to flatten sooner (<0.05 SOL) without over-trading.
- Add an optional “inventory decay” helper that triggers passive hedges after N seconds even if guard is active (currently 8 s timeout with 0.11 SOL clip ceiling).

### 4. Fee Resilience Checks
- Extend `analysis/regime_analysis.py` or a notebook to simulate maker fee rates (2–4 bps) over the realized PnL windows.
- Produce a table summarising fee-adjusted hourly PnL so we know the cushion required for premium mode.

### 5. Monitoring & Validation
- After each change, grab fresh 5-minute slices (`export_pnl_windows.py`) and rerun regime analysis.
- Track guard activity, realized vs. unrealized PnL, and inventory dwell times to confirm improvements.
- Document results in `docs/analysis/sol_regimes.md` and update this plan with findings.
- Monitor the new `maker_fifo_realized_quote` telemetry gauge (and per-market variants) to validate FIFO profits during stressed periods.

### 6. Optional Explorations
- Evaluate auto-notional capping during illiquidity (thin book snapshots).
- Backtest “inverse strategy” idea once baseline is profitable—easier to reason about from the same datasets.


