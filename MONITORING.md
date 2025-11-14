# Monitoring Guide

**Complete guide for monitoring your lighter bot in production.**

---

## Quick Health Checks

### 1. Health Endpoint (Easiest)

```bash
curl https://your-app.railway.app/health

# Should return:
# {"status": "healthy", "ws_age_seconds": <60, "quote_age_seconds": <60}
```

**Red flags:**
- `status: "unhealthy"`
- `ws_age_seconds > 60` (WebSocket disconnected)
- `quote_age_seconds > 60` (Maker engine stopped)
- 503 error (bot crashed)

### 2. Metrics Endpoint

```bash
curl https://your-app.railway.app/metrics | grep -E "(uptime|age|error)"
```

**Check for:**
- `uptime_seconds` - Should keep increasing
- `ws_age_seconds` - Should be < 60
- `quote_age_seconds` - Should be < 60
- Any `error` counters increasing

---

## Automated Monitoring Setup

### Option 1: UptimeRobot (Free - Recommended)

1. **Sign up**: https://uptimerobot.com
2. **Add Monitor**:
   - Type: HTTP(s)
   - URL: `https://your-app.railway.app/health`
   - Interval: 5 minutes
   - Alert contacts: Your email
3. **Get alerts** when bot goes down

### Option 2: Railway Built-in Monitoring

1. Go to Railway dashboard → Your service
2. "Metrics" tab shows:
   - CPU usage
   - Memory usage
   - Request rate

### Option 3: Custom Health Check Script

```bash
#!/bin/bash
# health_check.sh

URL="https://your-app.railway.app/health"
RESPONSE=$(curl -s $URL)

if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
    echo "✅ Bot is healthy"
    exit 0
else
    echo "❌ Bot is unhealthy!"
    echo "$RESPONSE"
    exit 1
fi
```

Run periodically:
```bash
watch -n 300 ./health_check.sh  # Check every 5 minutes
```

---

## Log Monitoring

### Railway Dashboard

1. Go to Railway → Your service → "Deployments" → Latest → "View Logs"
2. Search for errors: `ERROR`, `WARNING`, `Exception`, `Traceback`
3. Filter by component:
   - `[maker]` - Maker engine issues
   - `[listener]` or `[router]` - WebSocket issues
   - `[guard]` - Guard blocking issues

### What's Normal

✅ **Good signs:**
```
[INFO] [maker] [market:market:1] mid=... | bid=... | ask=...
[INFO] [listener] [router] mid updated market:1 -> ...
```

⚠️ **Occasional warnings (OK):**
- WebSocket reconnects (network hiccups)
- Occasional guard blocks (safety working)
- Cancel throttling (rate limit protection)

❌ **Bad signs:**
```
ERROR
WARNING (frequent)
Exception
Traceback
Connection refused
Timeout
Failed to connect
Kill-switch
```

---

## Key Issues to Watch For

### 1. WebSocket Disconnection

**Symptoms:**
- `ws_age_seconds > 60` in health endpoint
- No `[router] mid updated` logs
- Logs show "disconnected" or "reconnect"

**What to do:**
- Check if Lighter.xyz WebSocket is down
- Bot should auto-reconnect (check logs)
- If persistent, check Railway logs for errors

### 2. Maker Engine Stopped

**Symptoms:**
- `quote_age_seconds > 60` in health endpoint
- No `[maker]` logs for > 1 minute
- No quote updates

**What to do:**
- Check logs for errors in `[maker]`
- Look for "quote blocked" messages (guard blocking)
- Check if throttled (cancel limit exceeded)

### 3. Guard Blocking Quotes

**Symptoms:**
- Logs show: `[maker] quote blocked by guard`
- Frequent blocking messages
- No quotes being generated

**What to do:**
- Check inventory levels
- Check if price bands too tight
- Review guard config in `config.yaml`

### 4. High Cancel Rate

**Symptoms:**
- Logs show: `[maker] cancel limit exceeded`
- `[maker] throttled due to cancel limit`
- Quotes stop refreshing

**What to do:**
- Normal if it happens occasionally
- If frequent, may need to adjust `maker.limits.max_cancels`
- Check if chaos injector is enabled (should be false in production)

### 5. Bot Crashed

**Symptoms:**
- Health endpoint returns 503 or connection refused
- No logs for > 1 minute
- Railway shows "crashed" status

**What to do:**
- Check Railway logs for error traceback
- Look for Python exceptions
- Check if out of memory (Railway metrics)
- Restart service in Railway

---

## Regular Monitoring Routine

### Daily Checks (2 minutes)

1. **Health endpoint**: `curl https://your-app.railway.app/health`
2. **Quick log scan**: Railway → Logs → Look for red text
3. **UptimeRobot**: Check if any alerts

### Weekly Deep Dive (10 minutes)

1. **Review logs** for patterns:
   - Any recurring errors?
   - Guard blocks increasing?
   - Cancel throttling frequent?
2. **Check metrics**:
   - Uptime trends
   - Error rates
   - Performance
3. **Review config**: Any settings need adjustment?

---

## Quick Diagnostic Commands

### Check if bot is responding:
```bash
curl -s https://your-app.railway.app/health | jq .
```

### Check uptime:
```bash
curl -s https://your-app.railway.app/metrics | grep uptime_seconds
```

### Check WebSocket age:
```bash
curl -s https://your-app.railway.app/health | jq .ws_age_seconds
```

### Check quote age:
```bash
curl -s https://your-app.railway.app/health | jq .quote_age_seconds
```

---

## Red Flags Summary

**Immediate action needed:**
- ❌ Health endpoint returns 503
- ❌ `ws_age_seconds > 300` (5 minutes)
- ❌ `quote_age_seconds > 300` (5 minutes)
- ❌ Logs show "Kill-switch" messages
- ❌ Bot crashed/restarting repeatedly

**Monitor closely:**
- ⚠️ Frequent guard blocks
- ⚠️ Cancel throttling happening often
- ⚠️ WebSocket reconnecting frequently
- ⚠️ High error rate in logs

**Normal/OK:**
- ✅ Occasional guard blocks (safety working)
- ✅ Occasional cancel throttling (rate limit protection)
- ✅ WebSocket reconnects (network hiccups)
- ✅ Logs show normal quote generation

---

## When to Worry

**Don't worry about:**
- Occasional guard blocks (safety feature)
- Single errors that don't repeat
- WebSocket reconnects (auto-recovery works)
- Cancel throttling (rate limit protection)

**Do worry about:**
- Bot completely down (no health response)
- Repeated crashes
- Kill-switch triggered
- No quotes for > 5 minutes
- Continuous errors in logs

---

**Your bot is designed to be resilient - most issues self-resolve. The health endpoint is your best friend for quick checks!** 🎯

