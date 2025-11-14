## SOL Regime Analysis Workflow

Goal: correlate the bot’s realized PnL with SOL market conditions (trend, volatility, liquidity) to guide adaptive tuning.

### 1. Collect Market Data
- Prefer Lighter candles to stay venue-consistent:
  ```bash
  python scripts/fetch_candles.py \
    --market-id 2 \
    --interval 1m \
    --limit 1440 \
    --output data/analysis/sol_candles_1m.json
  ```
- If Lighter data is unavailable, fall back to Binance `SOLUSDT` klines and document the source.

### 2. Export PnL Windows
- Convert the metrics ledger into fixed windows (default 5 minutes):
  ```bash
  python scripts/export_pnl_windows.py \
    --ledger data/metrics/fills.jsonl \
    --window 300 \
    --market-id market:2 \
    --output data/analysis/sol_pnl_5m.csv
  ```
- Output columns include realized quote, fees, maker/taker/hedger volumes, base delta, fill counts.

### 3. Join & Analyze
- Load both datasets into a notebook (e.g. `notebooks/sol_regime.ipynb`):
  - Compute rolling volatility from candles (`log_return` σ).
  - Derive momentum/trend scores (EMA slope, price change over window).
  - Merge with PnL windows on timestamp buckets.
- Plot realized PnL vs. volatility/trend bins, guard activations, inventory excursions.

### 4. Derive Actions
- Identify regimes where realized PnL is negative and codify responses:
  - Widen spread or pause one side when trend exceeds threshold.
  - Relax/tighten guard floor depending on volatility.
  - Adjust hedger slippage caps for high-volatility slices.

### 5. Persist Results
- Keep raw exports under `data/analysis/`.
- Document findings, thresholds, and proposed code changes in this directory to ensure reproducibility.

Next steps: build the exploration notebook and automate daily refreshes once the pipeline proves useful.

---

### 2025-11-12 Findings Snapshot

- Dataset: `data/analysis/pnl_5m.csv` (5 m windows) joined with Binance `SOLUSDT` 1 m klines (`data/analysis/binance_solusdt_1m.json`).
- Realized PnL clusters:
  - Up-trend (> +0.1%) windows averaged **+16 quote** (favorable).
  - Down-trend (< –0.1%) windows averaged **–13 quote** (problematic).
  - Low-vol (≤ 0.0006) yielded **+5.36 quote**; mid/high volatility buckets drifted negative.
- Inventory correlation: realized PnL vs. base delta shows coefficient ≈ –1.0, confirming exposure direction drives the bleed.

**Adjustments in flight**
- Maker trend filter now biases to asks during down-trend (–10 bps trigger) and adds extra spread to avoid catching falling knives.
- High-volatility clip multiplier (0.85 once σ ≥ 9 bps) keeps maker size near exchange minimum when ranges widen.
- Hedger clips inventory faster (`trigger_units: 0.05`, `target_units: 0.02`) and falls back to aggressive crosses if exposure persists for 15 s.

Next validation: rerun `analysis/regime_analysis.py` after the next live block, capture fee-adjusted summaries, and record deltas here.

