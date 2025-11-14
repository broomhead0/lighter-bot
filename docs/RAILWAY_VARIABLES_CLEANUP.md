# Railway Variables Cleanup Status

## Summary

Attempted to delete 26 Railway environment variables that override trading parameters, but Railway CLI does not support deletion. However, **these variables are already being ignored** by the bot code, so they are effectively harmless.

## Variables That Should Be Deleted

These 26 variables exist in Railway but are **ignored by the bot** (code no longer reads them):

### Hedger Variables (9)
- `HEDGER_TRIGGER_UNITS`
- `HEDGER_TRIGGER_NOTIONAL`
- `HEDGER_TARGET_UNITS`
- `HEDGER_MAX_CLIP_UNITS`
- `HEDGER_PASSIVE_WAIT_SECONDS`
- `HEDGER_COOLDOWN_SECONDS`
- `HEDGER_PASSIVE_OFFSET_BPS`
- `HEDGER_PRICE_OFFSET_BPS`
- `HEDGER_MAX_SLIPPAGE_BPS`

### Maker Variables (13)
- `MAKER_SPREAD_BPS`
- `MAKER_INVENTORY_SOFT_CAP`
- `MAKER_SIZE`
- `MAKER_SIZE_MIN`
- `MAKER_SIZE_MAX`
- `MAKER_EXCHANGE_MIN_NOTIONAL`
- `MAKER_EXCHANGE_MIN_SIZE`
- `MAKER_LIMITS_MAX_CANCELS`
- `MAKER_LIMITS_MAX_LATENCY_MS`
- `MAKER_PAIR`
- `MAKER_PRICE_SCALE`
- `MAKER_RANDOMIZE_BPS`
- `MAKER_REFRESH_SECONDS`
- `MAKER_SIZE_SCALE`

### Guard Variables (3)
- `GUARD_PRICE_BAND_BPS`
- `GUARD_MAX_POSITION_UNITS`
- `GUARD_MAX_INVENTORY_NOTIONAL`

## Current Status

- ✅ **Code fixed**: `core/main.py` no longer reads these variables (removed from `_apply_env_overrides()`)
- ✅ **Bot working**: Bot is using values from `config.yaml` (single source of truth)
- ⚠️ **Variables still exist**: Railway CLI does not support deletion, but this is harmless

## How to Delete (Manual)

Since Railway CLI doesn't support deletion, you need to use the **Railway Web Interface**:

1. Go to [Railway Dashboard](https://railway.app)
2. Navigate to your project → `lighter-bot` service
3. Click on **Variables** tab
4. For each variable listed above:
   - Click the three-dot menu (⋮) next to the variable
   - Select **Delete**
   - Confirm deletion

**Note**: This is optional - the bot will work fine even if these variables remain, since the code no longer reads them.

## Verification

The bot is using values from `config.yaml`. To verify:

1. Check `config.yaml` for trading parameters
2. Check logs on startup - modules log their config (e.g., hedger logs `trigger_units`, `max_clip_units`)
3. Verify behavior matches `config.yaml` values

## Result

Even though the Railway variables still exist, **they are harmless** because:
- The bot code no longer reads them (removed from `_apply_env_overrides()`)
- All trading parameters come from `config.yaml` (version controlled)
- Single source of truth is established

Deleting them via web interface is recommended for cleanliness, but not required for functionality.

