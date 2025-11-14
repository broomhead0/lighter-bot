# Configuration Audit - Potential Gotchas

## Executive Summary

Audit of all configuration sources to identify places where settings might be hidden, overridden, or forgotten. This document tracks gotchas that could cause confusion when context reloads.

---

## ✅ Fixed Issues

### 1. Railway Env Overrides for Trading Parameters
**Status**: ✅ FIXED
**Problem**: Railway environment variables were overriding `config.yaml` for:
- `HEDGER_TRIGGER_UNITS`, `HEDGER_MAX_CLIP_UNITS`, `HEDGER_TARGET_UNITS`, etc.
- `MAKER_SPREAD_BPS`, `MAKER_INVENTORY_SOFT_CAP`, etc.

**Fix**: Removed env override code for all trading parameters. Only runtime toggles (dry_run, enabled) and secrets remain.

**Reference**: `docs/CONFIG_STRATEGY.md`, commit `0b4eb2d`

### 2. Guard Trading Parameters Override
**Status**: ✅ FIXED (code only; Railway vars still exist but are ignored)
**Problem**: `GUARD_PRICE_BAND_BPS`, `GUARD_MAX_POSITION_UNITS`, `GUARD_MAX_INVENTORY_NOTIONAL` were being overridden by Railway.

**Fix**: Removed env override code for guard trading parameters. Only safety toggles (kill_on_*, crossed_book_protection) remain.

**Railway vars to ignore** (will be ignored, but can be deleted):
- `GUARD_PRICE_BAND_BPS` (currently `35`)
- `GUARD_MAX_POSITION_UNITS` (currently `0.35`)
- `GUARD_MAX_INVENTORY_NOTIONAL` (currently `55`)

---

## ⚠️ Known Gotchas (Acceptable But Documented)

### 1. Hardcoded Defaults in Modules
**Status**: ⚠️ ACCEPTABLE (documented)
**Location**: All modules use `.get("key", default)` with fallback values.

**Examples**:
- `maker_engine.py`: `maker_cfg.get("spread_bps", 10.0)`
- `hedger.py`: `hedger_cfg.get("trigger_units", 0.05)`
- `self_trade_guard.py`: `cfg.get("price_band_bps", 50)`

**Why Acceptable**:
- Config should always be complete (we load from `config.yaml`)
- Defaults only fire if config is missing/invalid (fail-safe)
- All critical values are in `config.yaml` (version controlled)

**Gotcha**: If a config key is missing, a default will silently be used. Always ensure `config.yaml` is complete.

**Mitigation**: Config validation could warn on missing keys, but not currently implemented.

### 2. WS URL Fallback to Environment
**Status**: ⚠️ ACCEPTABLE (documented)
**Location**: `modules/market_data_listener.py:48`

```python
self.ws_url = ws_cfg.get("url") or os.environ.get("WS_URL")
```

**Why Acceptable**:
- WS URL might vary by environment (dev vs prod)
- `config.yaml` has it, but env override is useful for Railway secrets

**Gotcha**: If both are missing, `ws_url` will be `None` and connection will fail (fail-fast, so acceptable).

**Mitigation**: This is documented and intentional for deployment flexibility.

### 3. Fee Config Overrides
**Status**: ⚠️ ACCEPTABLE (documented)
**Location**: `core/main.py` lines 193-196

```python
(("fees", "maker_actual_rate"), "FEES_MAKER_ACTUAL_RATE", "float"),
(("fees", "taker_actual_rate"), "FEES_TAKER_ACTUAL_RATE", "float"),
(("fees", "maker_premium_rate"), "FEES_MAKER_PREMIUM_RATE", "float"),
(("fees", "taker_premium_rate"), "FEES_TAKER_PREMIUM_RATE", "float"),
```

**Why Acceptable**:
- Fees vary by account type (free vs premium)
- Might want to switch accounts without redeploying
- These are infrastructure-level settings, not trading parameters

**Gotcha**: If Railway has fee vars, they'll override `config.yaml`. This is intentional for account switching.

**Mitigation**: Documented. Consider removing these overrides if we never switch accounts dynamically.

---

## 🔍 Configuration Sources (In Priority Order)

1. **`config.yaml`** (PRIMARY SOURCE)
   - All trading parameters MUST be here
   - Version controlled, visible in git
   - Single source of truth for trading logic

2. **Environment Variables** (OVERRIDES - limited scope)
   - ✅ **Allowed**: Secrets (API keys, tokens)
   - ✅ **Allowed**: Account IDs (`ACCOUNT_INDEX`, `API_KEY_INDEX`)
   - ✅ **Allowed**: Runtime toggles (`MAKER_DRY_RUN`, `HEDGER_ENABLED`)
   - ✅ **Allowed**: Infrastructure (`TELEMETRY_PORT`, `WS_URL`)
   - ✅ **Allowed**: Fees (for account switching)
   - ❌ **Not Allowed**: Trading parameters (maker/hedger/guard config)

3. **Hardcoded Defaults** (FALLBACK ONLY)
   - Only fire if config is missing/invalid
   - Should never happen in production (config.yaml is always present)
   - Documented in code comments

---

## 📋 Railway Variables Audit

### Variables That SHOULD Be in Railway

**Secrets** (never in git):
- `API_KEY_PRIVATE_KEY`
- `WS_AUTH_TOKEN`
- `DISCORD_WEBHOOK`

**Account Identifiers**:
- `ACCOUNT_INDEX`
- `API_KEY_INDEX`
- `MAX_API_KEY_INDEX`

**Runtime Toggles** (might want to flip quickly):
- `MAKER_DRY_RUN`
- `HEDGER_DRY_RUN`
- `HEDGER_ENABLED`
- `GUARD_KILL_ON_CROSSED_BOOK`
- `GUARD_KILL_ON_INVENTORY_BREACH`

**Infrastructure**:
- `TELEMETRY_PORT`
- `WS_URL` (might vary by environment)
- `APP_LOG_LEVEL`

**Fees** (for account switching):
- `FEES_MAKER_ACTUAL_RATE`
- `FEES_TAKER_ACTUAL_RATE`
- `FEES_MAKER_PREMIUM_RATE`
- `FEES_TAKER_PREMIUM_RATE`

### Variables That Should NOT Be in Railway (Will Be Ignored)

**Trading Parameters** (use `config.yaml` instead):
- `HEDGER_TRIGGER_UNITS`
- `HEDGER_MAX_CLIP_UNITS`
- `HEDGER_TARGET_UNITS`
- `HEDGER_TRIGGER_NOTIONAL`
- `HEDGER_PASSIVE_WAIT_SECONDS`
- `HEDGER_COOLDOWN_SECONDS`
- `MAKER_SPREAD_BPS`
- `MAKER_INVENTORY_SOFT_CAP`
- `MAKER_SIZE`, `MAKER_SIZE_MIN`, `MAKER_SIZE_MAX`
- `GUARD_PRICE_BAND_BPS`
- `GUARD_MAX_POSITION_UNITS`
- `GUARD_MAX_INVENTORY_NOTIONAL`

**Status**: These will be ignored by the code (env override removed). Can be deleted from Railway, but not required.

---

## 🎯 Recommendations

### Immediate Actions
1. ✅ **Done**: Remove env overrides for trading parameters
2. ✅ **Done**: Document configuration strategy
3. ⚠️ **Optional**: Delete Railway vars that are now ignored (not required, but cleaner)

### Future Improvements
1. **Config Validation**: Add validation to warn on missing keys in `config.yaml`
2. **Config Schema**: Consider using a schema (e.g., `pydantic`) to enforce config structure
3. **Fee Override Decision**: Decide if fee overrides are needed, or remove them if not
4. **Documentation**: Ensure all trading parameters are documented in `config.yaml` comments

---

## 🔄 How to Verify Config is Correct

1. **Check `config.yaml`**: All trading parameters should be here
2. **Check Railway vars**: Only secrets, toggles, and infrastructure should be present
3. **Check logs**: On startup, modules log their config (e.g., hedger logs `trigger_units`, `max_clip_units`)
4. **Verify behavior**: If behavior doesn't match `config.yaml`, check logs for what values are actually used

---

## 📝 Quick Reference

**To change trading parameters**:
1. Edit `config.yaml`
2. Commit and push
3. Railway auto-deploys
4. Check logs to verify

**To quickly disable trading**:
1. Set `MAKER_DRY_RUN=true` in Railway (or `HEDGER_ENABLED=false`)
2. No redeploy needed

**To switch accounts**:
1. Update `ACCOUNT_INDEX` in Railway
2. Update fee env vars if switching account types
3. No redeploy needed

