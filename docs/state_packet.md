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
  - `maker.volatility` halflife 45 s, pauses at 30 bps until vol recovers and inventory < 25 % of soft cap
  - `maker.trend` filter (45 s lookback, +/-12 bps trigger, resumes at 6 bps, extra spread 2.5 bps, bid/ask gating)
  - `hedger` live (dry_run false): `trigger_units` 0.07, `target_units` 0.03, `max_clip_units` 0.08, `max_slippage_bps` 7, prefers passive, waits 0.4 s at 2 bps offset before crossing
  - `guard.max_position_units` 0.3, `guard.max_inventory_notional` 50, 5 s backoff on block
  - `metrics` ledger enabled (`data/metrics/fills.jsonl`, 5 MB rotation, 6 h rolling window)
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
  - Dashboard work: expose 5 min window metrics via `metrics_tool window --seconds 300` (requires restoring `railway ssh`) and surface in docs/gauges for quick sanity checks.
  - Scale size & pursue premium after step 5 succeeds; update this packet as thresholds change.


