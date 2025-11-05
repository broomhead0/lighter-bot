# 🚀 Quick Deployment Guide (Beginner-Friendly)

## Step 1: Choose Your Platform (5 minutes)

**I recommend Railway** - it's the easiest for beginners!

1. Go to: https://railway.app
2. Click "Start a New Project"
3. Sign up with GitHub (free)
4. Done! ✅

## Step 2: Prepare Your Code (2 minutes)

Make sure your code is on GitHub:

```bash
# If not already on GitHub:
git add .
git commit -m "Ready for deployment"
git push origin main
```

## Step 3: Deploy on Railway (10 minutes)

### A. Connect Repository

1. In Railway dashboard, click "New Project"
2. Select "Deploy from GitHub repo"
3. Find and select your `lighter-bot` repository
4. Click "Deploy Now"

### B. Configure Environment Variables

Railway will start building. While it builds:

1. Click on your new service
2. Go to "Variables" tab
3. Add these variables (click "New Variable" for each):

```
PYTHONPATH = /app
PYTHONUNBUFFERED = 1
LOG_LEVEL = INFO
WS_URL = wss://mainnet.zklighter.elliot.ai/stream/market_stats:all
```

**Optional** (if you have API keys):
```
API_KEY = your_key_here
API_SECRET = your_secret_here
DISCORD_WEBHOOK = your_webhook_url
```

### C. Update Config

Railway will use your `config.yaml`. But we need to update it for production:

1. In Railway, go to "Settings" → "Source"
2. Click "Edit Config" (or edit locally and push)
3. Make sure these are set:
   - `replay.enabled: false`
   - `chaos.enabled: false`
   - `telemetry.enabled: true`

### D. Wait for Deployment

- Railway will build your Docker image (takes 2-5 minutes)
- Watch the "Deployments" tab for progress
- Green checkmark = success! ✅

## Step 4: Get Your URL (1 minute)

1. In Railway, click your service
2. Go to "Settings" → "Networking"
3. Click "Generate Domain"
4. Copy your URL (e.g., `https://lighter-bot.railway.app`)

## Step 5: Test It! (2 minutes)

```bash
# Test health endpoint
curl https://your-app.railway.app/health

# Should return:
# {"status": "healthy", ...}

# Check metrics
curl https://your-app.railway.app/metrics
```

## Step 6: Monitor (Ongoing)

1. **View Logs**: Railway dashboard → "Deployments" → Click latest → "View Logs"
2. **Set Up Alerts**:
   - Go to https://uptimerobot.com (free)
   - Add monitor for your health endpoint
   - Get email alerts if it goes down

## 🎉 That's It!

Your bot is now live in production!

## 📋 Quick Checklist

Before going live with real money:

- [ ] Test with `maker.dry_run: true` first
- [ ] Monitor logs for 24 hours
- [ ] Verify health endpoint responds
- [ ] Set up uptime monitoring
- [ ] Test Discord alerts (if configured)
- [ ] Only then: Set `maker.dry_run: false`

## 🆘 Troubleshooting

**"Build failed"**
- Check Railway logs for errors
- Make sure Dockerfile is correct
- Verify all files are in repository

**"Container crashes"**
- Check logs in Railway dashboard
- Verify config.yaml is valid
- Check environment variables are set

**"Health endpoint not working"**
- Make sure `telemetry.enabled: true` in config
- Wait 30 seconds after deployment (startup time)
- Check Railway networking settings

## 💡 Pro Tips

1. **Start in dry-run mode**: Test everything before using real money
2. **Watch logs closely**: First 24 hours are critical
3. **Set up monitoring**: UptimeRobot is free and easy
4. **Keep config simple**: Don't enable all features at once
5. **Backup your config**: Save production config somewhere safe

## 📚 Need More Help?

- See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed guide
- See [PRE_DEPLOYMENT.md](PRE_DEPLOYMENT.md) for checklist
- Railway docs: https://docs.railway.app

Good luck! 🚀

