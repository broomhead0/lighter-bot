## Regime Response Plan (2025-11-12)

**Objective:** Turn the regime study into concrete maker/hedger changes that push realized PnL back to neutral/positive before enabling premium fees.

### 1. Trend-Gated Quoting
- Gate or widen the “danger side” whenever 5-minute return is below –6 bps, and pause bid quoting for `down_cooldown_seconds` (45 s) after a trigger (config knob baked into this branch).
- Leverage existing `maker.trend` block: down-threshold, extra spread additive, and telemetry for guard/cooldown (`maker_trend_down_guard`, `maker_trend_down_cooldown_active`).
- Upcoming: add a symmetric “uptrend” profile that loosens spreads and restores clips when market+PnL signals are favorable.

### 2. Volatility-Aware Clip Scaling
- Use minute-level realized vol from `MakerEngine._latest_volatility_bps`.
- Introduce a second size curve: shrink clips toward exchange minimum as vol crosses the 75th percentile (~0.0009) and pause sizing increases until vol relents.
- Maintain compatibility with guard scaling and lot quantisation.

### 3. Hedger Tightening / Safeguard
- Defensive baseline: `max_clip_units` 0.11, timeout 8 s, telemetry `hedger_force_aggressive`.
- ✅ Guard-aware safeguard: if `maker_guard_block_active` persists ≥10 s, hedger skips passive, boosts clip ×1.4, adds +6 bps cross, and re-arms after 0.75 s (telemetry `hedger_guard_emergency`).
- Next tuning: adjust timeout / multiplier based on guard dwell logs to avoid over-trading during brief halts.

### 4. Fee Resilience Checks
- Extend `analysis/regime_analysis.py` or a notebook to simulate maker fee rates (2–4 bps) over the realized PnL windows.
- Produce a table summarising fee-adjusted hourly PnL so we know the cushion required for premium mode.

### 5. Regime Detection (New)
- Build a small detector that classifies the tape into down vs. up/neutral using 1–5 minute returns, realized vol, and FIFO maker PnL.
- When signals flip “up”, switch to an aggressive profile (larger clips, faster cooldown reset); when signals flip “down”, activate the defensive profile above.
- Persist both parameter sets and detector thresholds; log switches so we can validate during post-mortems.
- Continue using `maker_fifo_realized_quote` + guard telemetry to confirm the detector selects the right profile.

### 6. Optional Explorations
- Evaluate auto-notional capping during illiquidity (thin book snapshots).
- Backtest “inverse strategy” idea once baseline is profitable—easier to reason about from the same datasets.


