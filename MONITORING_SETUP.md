# Quick Monitoring Setup Guide

## Step 1: Set Up UptimeRobot (5 minutes)

### 1.1 Sign Up
1. Go to: https://uptimerobot.com
2. Click "Sign Up" (top right)
3. Create free account (email + password)
4. Verify email if needed

### 1.2 Add Monitor
1. Click "Add New Monitor" (big orange button)
2. Fill in:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: `Lighter Bot Health`
   - **URL**: `https://lighter-bot-production.up.railway.app/health`
   - **Monitoring Interval**: 5 minutes (default)
   - **Alert Contacts**: Select your email
3. Click "Create Monitor"

### 1.3 Done!
- You'll get email alerts if bot goes down
- Dashboard shows bot status
- Free plan includes 50 monitors (plenty!)

## Step 2: Quick Health Check

Test your health endpoint:

```bash
curl https://lighter-bot-production.up.railway.app/health
```

Should return: `{"status": "healthy", ...}`

## Step 3: Check Logs (Railway)

### Quick Log Check:
1. Go to: https://railway.app
2. Click your project
3. Click your service
4. Go to "Deployments" → Latest deployment
5. Click "View Logs"
6. Scroll to bottom (most recent)
7. Look for:
   - ✅ `[maker]` messages (quotes being generated)
   - ❌ Any `ERROR` messages
   - ⚠️ Any `WARNING` messages (normal if occasional)

### What's Normal:
- ✅ Quotes every 5 seconds: `[maker] [market:market:1] mid=...`
- ✅ Health messages
- ⚠️ Occasional "WebSocket stale" warnings (expected - fallback working)

### What to Worry About:
- ❌ Repeated errors
- ❌ Bot crashes/restarts
- ❌ Kill-switch messages
- ❌ No quotes for > 1 minute

## Step 4: Bookmark These

**Health Endpoint:**
```
https://lighter-bot-production.up.railway.app/health
```

**Metrics Endpoint:**
```
https://lighter-bot-production.up.railway.app/metrics
```

**Railway Dashboard:**
```
https://railway.app
```

**UptimeRobot Dashboard:**
```
https://uptimerobot.com
```

## Daily Routine

### Morning Check (30 seconds):
1. Check UptimeRobot dashboard (is it green?)
2. If red, check Railway logs

### Evening Check (1 minute):
1. Check health endpoint (curl or browser)
2. Quick log scan in Railway
3. Check UptimeRobot for any alerts

## Success Checklist

After setup, you should have:
- [x] UptimeRobot monitoring active
- [x] Health endpoint bookmarked
- [x] Railway dashboard accessible
- [x] Know how to check logs
- [x] Understand what's normal vs. concerning

## Troubleshooting

**UptimeRobot shows "Down":**
- Check Railway logs for errors
- Verify health endpoint manually
- Check if Railway service is running

**Health endpoint not responding:**
- Check Railway service status
- View logs for errors
- May need to restart service

**Too many alerts:**
- Adjust UptimeRobot alert frequency
- Check if issue is real or false positive
- Review MONITORING_GUIDE.md for details

---

**You're all set! Just check UptimeRobot and Railway logs daily. 🎉**

