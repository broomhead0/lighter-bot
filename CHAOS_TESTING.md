# Chaos Injector Testing Guide

## Overview

The chaos injector (M8) allows you to test system resilience by injecting various failure scenarios:

1. **Latency spikes** - Delays in frame processing
2. **Quote-width spikes** - Volatile market conditions
3. **Cancel-rate testing** - Force cancels to test cancel discipline
4. **Reconnect simulation** - Simulate WS disconnections (ready but not fully tested)

## Quick Start

### Enable Chaos in Config

```yaml
chaos:
  enabled: true
  latency:
    enabled: true
    probability: 0.1      # 10% chance per frame
    min_ms: 10.0
    max_ms: 100.0
  quote_width:
    enabled: true
    probability: 0.05     # 5% chance per quote
    min_bps: 20.0
    max_bps: 100.0
  cancel_rate:
    enabled: true
    force_cancels_per_min: 60
```

### Run Automated Tests

```bash
source .venv/bin/activate
export PYTHONPATH=.
python scripts/test_chaos.py
```

## Test Scenarios

### Test 1: Latency Spikes

**Purpose:** Test system behavior under network latency

```yaml
chaos:
  enabled: true
  latency:
    enabled: true
    probability: 0.3        # 30% chance (higher for testing)
    min_ms: 50.0
    max_ms: 200.0
    spike_probability: 0.05 # 5% chance of 10x spike
```

**Expected:**
- Logs show `[chaos] injecting latency: Xms`
- Replay may slow down when spikes occur
- Watchdogs should detect stale WS if latency is too high

### Test 2: Quote-Width Spikes

**Purpose:** Test maker behavior under volatile market conditions

```yaml
chaos:
  enabled: true
  quote_width:
    enabled: true
    probability: 0.2        # 20% chance (higher for testing)
    min_bps: 30.0
    max_bps: 80.0
```

**Expected:**
- Logs show `[chaos] QUOTE WIDTH SPIKE: X bps -> Y bps (+Z)`
- Maker quotes should widen significantly
- Self-trade guard should catch if spreads get too wide

### Test 3: Cancel-Rate Testing

**Purpose:** Test cancel discipline thresholds

```yaml
chaos:
  enabled: true
  cancel_rate:
    enabled: true
    force_cancels_per_min: 30  # Force 30 cancels/min
```

**Expected:**
- Logs show `[chaos] FORCE CANCEL (testing cancel discipline: X/Y per min)`
- Maker logs show `[maker] CHAOS: forcing cancel`
- If `maker.limits.max_cancels` is set low, maker should throttle

### Test 4: Combined Chaos

**Purpose:** Test multiple failure modes simultaneously

```yaml
chaos:
  enabled: true
  latency:
    enabled: true
    probability: 0.1
  quote_width:
    enabled: true
    probability: 0.05
  cancel_rate:
    enabled: true
    force_cancels_per_min: 60
```

## What to Look For

### Success Indicators

✅ Chaos injector initializes: `[chaos] injector initialized`
✅ Chaos logs appear during execution
✅ System continues operating despite chaos
✅ Guards/kill-switches trigger appropriately

### Validation Points

1. **Latency:** Watch replay timing - should see delays
2. **Quote-width:** Check maker logs for widened spreads
3. **Cancel-rate:** Verify cancel discipline limits are respected
4. **Guards:** Self-trade guard should catch invalid quotes
5. **Watchdogs:** Should detect stale states if chaos is too severe

## Integration with Replay

Chaos works best with replay mode:

```yaml
replay:
  enabled: true
  speed: 1.0

chaos:
  enabled: true
  latency:
    enabled: true
    probability: 0.1
```

This allows you to:
- Replay captured data at known speeds
- Inject predictable chaos scenarios
- Test system resilience in a controlled environment

## Troubleshooting

**Chaos not appearing:**
- Check `chaos.enabled: true` in config
- Verify specific chaos type is enabled (e.g., `latency.enabled: true`)
- Check probabilities aren't too low

**Too much chaos:**
- Lower probabilities (e.g., 0.01 instead of 0.1)
- Increase min/max intervals
- Reduce spike multipliers

**System crashes:**
- This is expected in extreme scenarios
- Check guards and kill-switches are working
- Adjust thresholds if needed

## Example Output

```
[chaos] injector initialized: latency=True reconnect=False quote=True cancel=True
[main] CHAOS INJECTOR enabled
[chaos] starting background chaos tasks
[chaos] injecting latency: 87.3ms
[chaos] QUOTE WIDTH SPIKE: 10.00 bps -> 65.43 bps (+55.43)
[chaos] FORCE CANCEL (testing cancel discipline: 1/60 per min)
[maker] CHAOS: forcing cancel (testing cancel discipline)
```

## Next Steps

After validating chaos injection:
1. Test with real captured data
2. Verify kill-switches trigger correctly
3. Validate cancel discipline thresholds
4. Test reconnect simulation with live WS
5. Document observed failure modes

