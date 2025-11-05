# 🚀 Deployment Steps - Let's Do This!

## Step 1: Railway Setup (5 minutes)

1. **Go to Railway**: https://railway.app
2. **Sign up/Login** with GitHub (free tier available)
3. **Click "New Project"** → **"Deploy from GitHub repo"**
4. **Select your repository**: `broomhead0/lighter-bot`
5. **Click "Deploy Now"**

Railway will start building your Docker image automatically!

## Step 2: Configure Environment Variables

While Railway builds, set up your environment variables:

1. **Click on your service** (the one that's building)
2. **Go to "Variables" tab**
3. **Click "New Variable"** and add these one by one:

### Required Variables:
```
PYTHONPATH = /app
PYTHONUNBUFFERED = 1
LOG_LEVEL = INFO
WS_URL = wss://mainnet.zklighter.elliot.ai/stream/market_stats:all
```

### Optional (if you have them):
```
API_KEY = your_lighter_api_key_here
API_SECRET = your_lighter_api_secret_here
DISCORD_WEBHOOK = your_discord_webhook_url
```

## Step 3: Wait for Build

- Railway will build your Docker image (2-5 minutes)
- Watch the "Deployments" tab for progress
- Green checkmark = success! ✅
- If it fails, check the logs

## Step 4: Get Your URL

1. **Click your service**
2. **Go to "Settings"** → **"Networking"**
3. **Click "Generate Domain"**
4. **Copy your URL** (e.g., `https://lighter-bot-production.up.railway.app`)

## Step 5: Test It!

Open your terminal and test:

```bash
# Test health endpoint
curl https://YOUR-URL.railway.app/health

# Should return:
# {"status": "healthy", "ws_age_seconds": ..., "quote_age_seconds": ..., "timestamp": ...}
```

## Step 6: Monitor Logs

1. **In Railway dashboard**, click your service
2. **Go to "Deployments"** → Click the latest deployment
3. **Click "View Logs"**
4. **Watch for**:
   - ✅ "lighter-bot starting"
   - ✅ "MakerEngine started"
   - ✅ "MarketDataListener started"
   - ❌ Any errors (red text)

## Step 7: Set Up Monitoring (Recommended)

1. **Go to**: https://uptimerobot.com (free)
2. **Sign up** (free account)
3. **Add Monitor**:
   - Type: HTTP(s)
   - URL: `https://YOUR-URL.railway.app/health`
   - Interval: 5 minutes
4. **Get alerts** if your bot goes down!

## ✅ Success Checklist

- [ ] Railway deployment successful (green checkmark)
- [ ] Health endpoint responds (`/health` returns JSON)
- [ ] Logs show bot starting successfully
- [ ] No errors in logs
- [ ] Uptime monitoring set up (optional but recommended)

## 🎉 You're Live!

Your bot is now running in production!

### What to Watch:

1. **First 24 hours**: Monitor logs closely
2. **Check health endpoint**: Every few hours
3. **Watch for Discord alerts**: If configured
4. **Verify maker is quoting**: Check logs for quote updates

### When Ready for Live Trading:

1. **Monitor for 24-48 hours** in dry-run mode
2. **Verify everything works** correctly
3. **Then** update config to `maker.dry_run: false`
4. **Or** set via Railway environment variable: `MAKER_DRY_RUN=false`

## 🆘 Troubleshooting

**Build fails?**
- Check Railway logs for errors
- Verify Dockerfile is correct
- Make sure all files are in GitHub

**Health endpoint not working?**
- Wait 30 seconds after deployment (startup time)
- Check Railway networking settings
- Verify `telemetry.enabled: true` in config

**Bot not starting?**
- Check Railway logs for errors
- Verify environment variables are set
- Check config.yaml is valid

**Need help?**
- Check Railway logs first
- See DEPLOYMENT.md for detailed guide
- Railway docs: https://docs.railway.app

Good luck! 🚀

