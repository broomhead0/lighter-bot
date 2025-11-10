## Metrics Revamp Plan

### Goals
- Single source of truth for realised PnL, mark-to-market, volume, drawdown, and Sharpe inputs.
- Persistence across restarts so the bot and telemetry agree with exchange stats.
- Ability to recompute for arbitrary time windows (e.g. “since inception” vs “last 6h”).
- Simple tooling (`scripts/metrics.py`) to inspect, reset, or export metrics.

### Architecture
1. **Ledger Layer (`metrics/ledger.py`)**
   - Appends every fill (maker & taker) to a durable JSON Lines file at `data/metrics/fills.jsonl`.
   - Stores: timestamp, market, side, role, size, price, fee, quote_delta, inventory snapshot.
   - Exposes append + read windowed iterators (time range, latest N fills).
   - Handles rotation (`max_bytes`, `max_days`) and optional in-memory cache for quick queries.

2. **Compositor (`metrics/compositor.py`)**
   - Consumes ledger events to compute:
     - realised PnL (sum quote deltas minus fees),
     - volume (maker/taker),
     - running inventory & mark-to-market,
     - drawdown series,
     - Sharpe inputs (mean/vol of daily PnL or hourly buckets).
   - Supports `window=all | last_hours | since_ts`.
   - Output is a dataclass + dict for telemetry.

3. **Ingestion hooks**
   - `AccountListener._handle_trade_entry` appends to the ledger instead of mutating `StateStore` PnL counters.
   - Hedger simulations optionally append synthetic fills (flagged `type="hedger_sim"`).

4. **Telemetry integration**
   - `periodic_core_metrics` calls compositor every 10s, pushes gauges prefixed with `metrics_*`.
   - Telemetry now reports both cumulative and 6h rolling stats by default.

5. **CLI tooling (`scripts/metrics_tool.py`)**
   - `dump` – show current totals (matching telemetry).
   - `window` – compute stats for a custom period.
   - `reset` – archive existing ledger (with confirmation) to start fresh.
   - `export` – write CSV for external analysis.
   - `import-json` – backfill trades exported via `fetch_trades.py --output` (fees derived from `config.fees`).
   - `compare` – (future) cross-check vs REST API summary.

6. **Persistence & Safety**
   - Ledger writes are synchronous to avoid data loss on crash.
   - Rotate archived files into `data/metrics/archive/` with timestamp.
   - Provide `metrics.enabled` config gate to disable if disk unavailable.

7. **Migration**
   - On first run, ingest existing telemetry CSV (if present) to pre-populate ledger (optional).
   - After deployment, remove deprecated PnL tracking code from `StateStore` once parity confirmed.

### Implementation Order
1. Build ledger module + unit tests (append/read/rotate).
2. Implement compositor + minimal statistics (realised, unrealised, volume).
3. Hook account listener -> ledger.
4. Update telemetry loop to consume compositor.
5. Ship CLI script.
6. Optional: add comparison tooling & remove legacy state counters.

