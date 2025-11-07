# Troubleshooting Guide

## UptimeRobot Alert: Monitor Down

### Quick Check

1. **Test health endpoint:**
   ```bash
   curl https://lighter-bot-production.up.railway.app/health
   ```

2. **If it's responding now:**
   - ✅ Likely a temporary restart (normal)
   - ✅ Bot auto-recovered
   - ✅ No action needed

3. **If it's still down:**
   - Check Railway logs for errors
   - See troubleshooting steps below

## Common Issues

### 1. Service Restart (Normal)

**Symptoms:**
- UptimeRobot alert
- Health endpoint returns healthy shortly after
- Uptime shows low number (recent restart)

**Cause:**
- Railway auto-restart
- Deployment/update
- Container restart

**Action:**
- ✅ Normal behavior
- ✅ Bot recovers automatically
- ✅ No action needed

### 2. Health Endpoint Not Responding

**Symptoms:**
- Health endpoint times out
- Metrics endpoint not responding
- Railway shows service running

**Check:**
1. Railway dashboard → Service → Status
2. Railway logs for errors
3. Check if service is actually running

**Fix:**
- Restart service in Railway
- Check logs for crash errors
- Verify port 9100 is accessible

### 3. Bot Crashed

**Symptoms:**
- Repeated errors in logs
- Service keeps restarting
- Health endpoint never recovers

**Check Railway Logs For:**
- Python exceptions
- Import errors
- Configuration errors
- Out of memory errors

**Fix:**
- Review error in logs
- Fix configuration if needed
- Restart service

### 4. WebSocket Issues

**Symptoms:**
- Warnings about WebSocket disconnection
- "falling back to synthetic feed" messages

**Action:**
- ✅ Normal behavior
- ✅ Bot continues with synthetic data
- ✅ No action needed

## Quick Diagnostic Commands

### Check Health
```bash
curl https://lighter-bot-production.up.railway.app/health
```

### Check Metrics
```bash
curl https://lighter-bot-production.up.railway.app/metrics
```

### Check Railway Status
1. Go to Railway dashboard
2. Click your service
3. Check "Status" (should be "Running")
4. Check "Deployments" for recent activity

## What to Check in Railway Logs

### Normal Messages:
- ✅ `[maker]` quotes every 5 seconds
- ✅ `[listener]` WebSocket attempts
- ✅ Health endpoint logs

### Problem Messages:
- ❌ Python tracebacks
- ❌ Import errors
- ❌ Configuration errors
- ❌ Repeated crashes
- ❌ Out of memory errors

## When to Worry

**Don't worry about:**
- ✅ Occasional service restarts
- ✅ WebSocket disconnections (fallback works)
- ✅ Occasional warnings

**Do worry about:**
- ❌ Service won't start
- ❌ Repeated crashes
- ❌ Health endpoint never recovers
- ❌ Errors in logs

## Recovery Steps

### If Service is Down:

1. **Check Railway Dashboard**
   - Is service running?
   - Any error messages?

2. **Check Logs**
   - Railway → Service → Deployments → View Logs
   - Look for errors at the end

3. **Restart Service**
   - Railway → Service → Settings → Restart
   - Or redeploy latest version

4. **Verify Health**
   - Wait 30 seconds
   - Check health endpoint
   - Should recover

## Prevention

- ✅ Monitor logs regularly
- ✅ Set up UptimeRobot alerts
- ✅ Check health endpoint daily
- ✅ Review errors promptly

---

**Most issues are temporary and auto-recover. If health endpoint is responding, you're good! 🚀**

