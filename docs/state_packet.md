## Bot State Packet (2025-11-10)

- **Repo**: `/Users/nico/cursour_lighter_bot/lighter-bot`
- **Active Market**: `market:102` (ICP) via profile `profiles/market_102.yaml`
- **Key Modules**:
  - `core/main.py` – orchestrates maker, hedger, account listener
  - `modules/maker_engine.py` – adaptive/volatility-aware quoting with notional clamp
  - `modules/hedger.py` – hedges toward `target_units`, respects `max_slippage_bps`
  - `modules/self_trade_guard.py` – guard rails activated via `guard.*` config
- **Critical Config (`config.yaml`)**:
  - `maker.size` 1.5 (`size_min` 1.36, `size_max` 1.63)
  - `maker.price_scale` 10000, `maker.size_scale` 100
  - `maker.exchange_min_notional` 10.0 (prevents `21706` errors)
  - `hedger.dry_run` false, `trigger_units` 1.36, `max_clip_units` 1.36, `price_offset_bps` 6
  - `guard.max_position_units` 20, `guard.max_inventory_notional` 150
  - `maker.volatility` block enabled (EMA halflife 30s, pause at 35 bps, resume at 20 bps)
- **Environment expectations**:
  - `WS_AUTH_TOKEN` stored in Railway & `.env.ws_token` (regenerate with `scripts/refresh_ws_token.py`)
  - `LIGHTER_API_BEARER` exported locally when running REST scripts
  - Railway service name: `lighter-bot`
- **Operational Commands**:
  - Deploy: `railway up`
  - Tail logs: `railway logs --service lighter-bot --lines 200`
  - Health probe: `railway run --service lighter-bot -- curl -sf http://127.0.0.1:8000/health`
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
- **Next Steps**:
  - Monitor ICP PnL over next session using `fetch_trades.py`
  - Continue tuning volatility multipliers if drawdown persists
  - Expand `profiles/` for future market rotations (`set_market.py --profile-out` saves baseline)


