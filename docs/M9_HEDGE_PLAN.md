## Hedging Module Plan (M9)

### Goals
- Automatically offset inventory drift as fills accumulate.
- Respect guard thresholds while minimizing execution cost.

### Key components
- **StateStore integration:** consume position data from `account_listener`.
- **Hedge strategy:** configurable — immediate hedge vs threshold-based.
- **Execution venue:** reuse `TradingClient` with maker offsets or taker orders.
- **Risk limits:** enforce notional caps and rate limits.
- **Telemetry & alerts:** track hedging activity, surface failures.

### Implementation steps
1. **Inventory watcher**
   - Poll or subscribe to StateStore inventory updates.
   - Emit telemetry metric `inventory_delta`.
2. **Threshold logic**
   - Config-driven thresholds (e.g., hedge when |inventory| exceeds 0.05 SOL).
   - Support hysteresis to avoid flip-flopping.
3. **Order placement**
   - Construct hedge orders via `TradingClient`; start with market order for speed, later optional limit strategy.
   - Ensure hedges respect guardrails and available margin.
4. **State updates**
   - Confirm fill using account stream; reconcile to ensure inventory neutralized.
5. **Failure handling**
   - Retry with exponential backoff.
   - Trigger alert when hedge fails beyond N retries.

### Configuration additions
```yaml
hedger:
  enabled: true
  market: market:2
  trigger_units: 0.18
  trigger_notional: 30
  target_units: 0.04
  max_clip_units: 0.07
  price_offset_bps: 10
  poll_interval_seconds: 1.0
  cooldown_seconds: 5.0
  max_attempts: 3
  retry_backoff_seconds: 2.0
```

