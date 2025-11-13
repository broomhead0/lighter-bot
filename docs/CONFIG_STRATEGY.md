# Configuration Strategy

## Single Source of Truth: config.yaml

**All trading parameters come from `config.yaml` (version controlled).**

### Why This Matters

- **Version controlled**: All config changes are in git, visible in commits
- **No context loss**: I (the AI) can see all config changes when reviewing code
- **No surprises**: Railway environment variables won't override config.yaml values
- **Easier debugging**: One place to check for all trading parameters

## What Changed

Removed Railway environment variable overrides for:
- `HEDGER_TRIGGER_UNITS`
- `HEDGER_TRIGGER_NOTIONAL`
- `HEDGER_TARGET_UNITS`
- `HEDGER_MAX_CLIP_UNITS`
- `HEDGER_PASSIVE_WAIT_SECONDS`
- `HEDGER_COOLDOWN_SECONDS`
- `MAKER_SPREAD_BPS`
- `MAKER_INVENTORY_SOFT_CAP`
- All other trading parameters

## What Still Uses Environment Variables

Only these should use Railway environment variables:
- **API keys/tokens** (secrets): `API_KEY_PRIVATE_KEY`, `WS_AUTH_TOKEN`, etc.
- **Account IDs**: `ACCOUNT_INDEX`, `API_KEY_INDEX`
- **Infrastructure**: `RAILWAY_*`, `TELEMETRY_PORT`, etc.
- **Runtime toggles**: `MAKER_DRY_RUN`, `HEDGER_DRY_RUN`, `HEDGER_ENABLED`

## How to Change Trading Parameters

1. **Edit `config.yaml`** - Make your changes
2. **Commit and push** - Changes are version controlled
3. **Railway auto-deploys** - No Railway variables needed
4. **Verify in logs** - Check hedger/maker config snapshot logs

## Railway Variables That Can Stay

These are fine to keep in Railway (runtime/infrastructure):
- `ACCOUNT_INDEX`, `API_KEY_INDEX` - Account identifiers
- `API_KEY_PRIVATE_KEY`, `WS_AUTH_TOKEN` - Secrets (should never be in git)
- `MAKER_DRY_RUN`, `HEDGER_DRY_RUN` - Safety toggles (might want to flip quickly)
- `HEDGER_ENABLED` - Enable/disable hedger without redeploy
- `TELEMETRY_ENABLED`, `TELEMETRY_PORT` - Infrastructure settings
- `APP_LOG_LEVEL` - Might want to change log level without redeploy

## Railway Variables to Remove/Clear

These should NOT be in Railway (they override config.yaml):
- `HEDGER_TRIGGER_UNITS`
- `HEDGER_MAX_CLIP_UNITS`
- `HEDGER_TARGET_UNITS`
- `HEDGER_TRIGGER_NOTIONAL`
- `HEDGER_PASSIVE_WAIT_SECONDS`
- `HEDGER_COOLDOWN_SECONDS`
- `MAKER_SPREAD_BPS`
- `MAKER_INVENTORY_SOFT_CAP`
- Any other trading parameters

To remove: Set them to empty string in Railway, or just leave them (they'll be ignored since the code no longer reads them).

## Code Changes

In `core/main.py`, `_apply_env_overrides()` no longer includes trading parameters. Only runtime toggles and secrets are overridden.

## Result

- ✅ All trading parameters in `config.yaml` (version controlled)
- ✅ No surprises from Railway variables
- ✅ Easier to track changes
- ✅ AI can see all config in context

