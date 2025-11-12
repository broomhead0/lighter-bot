## Bot State Packet (2025-11-10)

- **Repo**: `/Users/nico/cursour_lighter_bot/lighter-bot`
- **Active Market**: `market:2` (SOL) via profile `profiles/market_2.yaml`
- **Key Modules**:
  - `core/main.py` – orchestrates maker, hedger, account listener
  - `modules/maker_engine.py` – adaptive/volatility-aware quoting with notional clamp
  - `modules/hedger.py` – hedges toward `target_units`, respects `max_slippage_bps`
  - `modules/self_trade_guard.py` – guard rails activated via `guard.*` config
- **Critical Config (`config.yaml`)**:
  - `maker.size` 0.064 (`size_min` 0.061, `size_max` 0.072), exchange min size 0.061, notional floor 10.5
  - `maker.spread_bps` 12.0 baseline, volatility-aware band 7 → 13 bps, adaptive size multipliers 0.7 → 1.1, PnL guard can add up to +8 bps
  - `maker.volatility` halflife 45 s, pauses at 30 bps until vol recovers and inventory < 25 % of soft cap; additional high-vol clip multiplier 0.85 when 1 m σ > 9 bps (telemetry `maker_high_vol_clip_active`)
- `maker.trend` filter (45 s lookback, up-trend trigger +12 bps, down-trend trigger -6 bps biasing to asks, resumes at ±6 bps, extra spread +2.5 bps up/+6 bps down, bid cooldown driven by regime; telemetry `maker_trend_down_guard`, `maker_trend_down_cooldown_active`)
- `maker.regimes` dynamically flips between **defensive** (size ×0.7, +2 bps spread, 45 s cooldown) and **aggressive** (size ×1.0, tighter spread, 20 s cooldown) using the trend signal and guard state (telemetry `maker_regime_state`)
- Guard telemetry `maker_guard_block_active` raises when SelfTradeGuard suppresses posting; cleared once quotes resume to signal downstream safeguards.
  - `hedger` live (dry_run false): `trigger_units` 0.05, `target_units` 0.02, `max_clip_units` 0.10, `max_slippage_bps` 12, prefers passive with 0.25 s wait @ 2 bps, forces aggressive cross after 8 s exposure; when maker PnL guard is active it dials clips to ×0.65, caps taker slippage at 9 bps, and crosses at 7 bps; guard safeguard still escalates after ≥10 s block (clip ×1.4, extra 6 bps cross, 0.75 s cooldown) with telemetry `hedger_force_aggressive` + `hedger_guard_emergency`
  - `guard.max_position_units` 0.3, `guard.max_inventory_notional` 50, 5 s backoff on block
  - `metrics` ledger enabled (`data/metrics/fills.jsonl`, 5 MB rotation, 6 h rolling window)
  - Telemetry exposes FIFO realized maker PnL via `maker_fifo_realized_quote` (plus per-market gauges)
- **Environment expectations**:
  - `WS_AUTH_TOKEN` stored in Railway & `.env.ws_token` (regenerate with `scripts/refresh_ws_token.py`)
  - `LIGHTER_API_BEARER` exported locally when running REST scripts
  - Railway service name: `lighter-bot`
- **Operational Commands**:
  - Deploy: `railway up`
  - Tail logs: `railway logs --service lighter-bot --lines 200`
  - Health probe: `railway run --service lighter-bot -- curl -sf http://127.0.0.1:8000/health`
  - Metrics ledger: `python scripts/metrics_tool.py dump` (or `window --hours 6`, `reset --confirm`, `import-json --input data/metrics/backfill.json`)
  - Dump telemetry: `railway ssh --service lighter-bot -- python scripts/dump_metrics.py --filter portfolio_`
  - Generate market profile: `python scripts/set_market.py --symbol SYMBOL --balance-usd 30 --sizing-multiplier 1.1 --profile-out profiles/market_<id>.yaml --activate`
  - Apply profile: `python scripts/apply_profile.py --profile profiles/market_<id>.yaml --config config.yaml --metadata-out data/instruments/market_<id>.json`
  - Refresh WS token: `python scripts/refresh_ws_token.py --config config.yaml --railway`
  - Fetch trades + PnL: `python scripts/fetch_trades.py --base-url https://mainnet.zklighter.elliot.ai --account 366110 --market-id 102 --limit 200 --mark-mid <mid> --token <bearer>`
  - Suggest markets: `python scripts/suggest_market_targets.py --top 10` (pass `--target-symbol SYMBOL` to inspect one)
- **Railway Auto-Deploy**: pushes to `main` auto-trigger deployment; verify with logs + `/health` immediately.
- **Data Retention**: Prometheus metrics & logs reset each deploy; fetch trade history for PnL comparisons.
- **Known Risks**:
  - Inventory drift if hedger throttled; monitor `hedger` logs and `guard` alerts.
  - Premium tier not enabled; maker fees assumed zero.
- **Positive-PnL Stabilization Plan**:
  1. **Edge First** – Widen base `maker.spread_bps` toward 12–15 bps, let volatility band tighten only when fills are profitable; clip sizes stay modest until realized ≥ 0 for 30 min.
  2. **Self-Healing Guard** – Add a short-window realized-PnL watchdog (5 min) that auto-widens spreads or trims size when consecutive slices go negative.
  3. **Hit Quality** – Track how often resting orders trade immediately; if we’re lone top-of-book/liquidity-taking, widen in real time and prioritize quoting the safe side.
  4. **Hedger as Alpha** – Keep passive-first hedging, but abandon the cross if spread move exceeds plan; optionally add a second resting tier to capture kickbacks.
  5. **Premium Only After Proof** – Flip fees + enlarge clips only once realized PnL runs neutral/positive with the guard engaged; re-evaluate every time we change markets.
  - **Recent Work (Nov 11)**:
    - Widened default spread to 12 bps and added PnL guard module (`MakerEngine.apply_pnl_guard`) with 5 minute realized floor.
    - Quantized guard-adjusted clip sizes to the exchange lot step to prevent `21706` errors.
    - Loosened hedger slippage/offset tolerances and temporarily raised guard limits to flush inventory during drawdowns.
    - Observed UI PnL stabilizing post-fix; current baseline keeps realized near zero while volatility settles.
  - Dashboard work: expose 5 min window metrics via `metrics_tool window --seconds 300` (requires restoring `railway ssh`) and surface in docs/gauges for quick sanity checks.
  - Scale size & pursue premium after step 5 succeeds; update this packet as thresholds change.

## SOL Regime Analysis Gameplan

Objective: understand when the bot makes/loses money by correlating realized PnL with SOL price action, volatility, and guard/hedger events.

1. **Data Collection**
   - Use Lighter REST candles for `market:2` (`/public/markets/{id}/candles?interval=1m`) to fetch OHLCV aligned with bot timestamps. Fallback: Binance `SOLUSDT` klines.
   - Export 5-minute slices from our ledger (fills + mids) using `metrics_tool.py window --seconds <window>` or by reading `data/metrics/fills.jsonl`.
   - Log guard activations, hedger crosses, and inventory peaks (already surfaced in logs/metrics).

2. **Feature Engineering**
   - Compute rolling realized volatility (σ of log returns) and classify trend strength (EMA slope or simple momentum).
   - Mark guard engagements, hedger taker fills, and inventory excursions per slice.
   - Derive spread capture vs. mid move (maker edge, hedger slippage) from ledger entries.

3. **Analysis Notebook**
   - Build a Jupyter notebook that joins PnL slices with candle features.
   - Plot realized PnL vs. volatility/trend buckets, guard frequency, hit quality, inventory duration.
   - Identify regimes where realized PnL is consistently negative (e.g., strong trend + low vol) to inform adaptive logic.

4. **Actionable Outputs**
   - Define heuristics: widen spreads or pause one side when trend > threshold, relax guard floor during chop, etc.
   - Prioritize changes that can run automatically via config or existing modules (trend filter, volatility block, guard settings).

5. **Persistence**
   - Store intermediate datasets (candles + PnL slices) under `data/analysis/`.
   - Document findings in a new `docs/analysis/sol_regimes.md` once complete.

Next: implement data-fetch script and analysis notebook after confirming plan.


