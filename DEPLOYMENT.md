# Deployment Guide

**Complete guide for deploying the lighter bot to production.**

---

## Quick Start (Railway - Recommended)

### Step 1: Sign Up & Deploy (5 minutes)

1. **Go to**: https://railway.app
2. **Sign up** with GitHub (free tier available)
3. **Create New Project** → "Deploy from GitHub repo"
4. **Select repository**: `broomhead0/lighter-bot`
5. **Click "Deploy Now"**

Railway will build your Docker image automatically!

### Step 2: Configure Environment Variables

While Railway builds, set up environment variables:

1. Click on your service → "Variables" tab
2. Add these variables:

```
PYTHONPATH = /app
PYTHONUNBUFFERED = 1
LOG_LEVEL = INFO
WS_URL = wss://mainnet.zklighter.elliot.ai/stream
```

**Optional** (for live trading):
```
API_KEY = your_lighter_api_key
API_SECRET = your_lighter_api_secret
DISCORD_WEBHOOK = your_discord_webhook_url
```

**Note:** You don't need API keys for initial deployment - bot runs in dry-run mode.

### Step 3: Update Config for Production

Edit `config.yaml` (or set via environment variables):

```yaml
replay:
  enabled: false  # Disable replay mode

chaos:
  enabled: false  # Disable chaos (unless testing)

telemetry:
  enabled: true  # Enable telemetry for health checks

alerts:
  enabled: true  # Enable alerts
```

### Step 4: Test Deployment

```bash
# Get your Railway URL (Settings → Networking → Generate Domain)
curl https://your-app.railway.app/health

# Should return: {"status": "healthy", ...}
```

### Step 5: Monitor

1. **View Logs**: Railway dashboard → Service → Deployments → Latest → View Logs
2. **Set Up Alerts**: Use UptimeRobot (free) - see Monitoring section below

**Done!** Your bot is now live. 🎉

---

## Alternative Platforms

### DigitalOcean App Platform

1. Sign up at https://www.digitalocean.com
2. Create App → Connect GitHub repository
3. Configure:
   - Build Command: (empty, Docker handles it)
   - Run Command: `python -m core.main`
   - Port: `9100`
4. Add environment variables (same as Railway)
5. Deploy

### AWS EC2

1. Launch EC2 instance (Ubuntu 22.04, t2.micro free tier)
2. Connect via SSH
3. Install Docker:
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose
   sudo usermod -aG docker ubuntu
   ```
4. Clone repository:
   ```bash
   git clone https://github.com/broomhead0/lighter-bot.git
   cd lighter-bot
   ```
5. Configure `config.yaml` for production
6. Deploy:
   ```bash
   docker-compose up -d
   ```
7. Configure security group to allow port 9100

### Render

1. Sign up at https://render.com
2. New Web Service → Connect GitHub
3. Configure:
   - Environment: Docker
   - Build Command: (auto-detected)
   - Start Command: `python -m core.main`
4. Add environment variables (same as Railway)
5. Deploy

---

## Production Configuration

### Required Settings

```yaml
# config.yaml
replay:
  enabled: false  # Must be false in production

telemetry:
  enabled: true  # Required for health checks
  port: 9100

app:
  log_level: INFO  # Or WARNING for less noise
```

### Using Environment Variables

Don't hardcode secrets in `config.yaml`. Use environment variables:

```yaml
# config.yaml
api:
  base_url: ${API_BASE_URL}
  key: ${API_KEY}

alerts:
  discord_webhook_url: ${DISCORD_WEBHOOK}
```

Set them in your deployment platform's environment variables.

---

## Monitoring Setup

### UptimeRobot (Free - Recommended)

1. **Sign up**: https://uptimerobot.com
2. **Add Monitor**:
   - Type: HTTP(s)
   - URL: `https://your-app.railway.app/health`
   - Interval: 5 minutes
   - Alert contacts: Your email
3. **Get alerts** when bot goes down

### Railway Built-in Monitoring

1. Go to Railway dashboard → Your service
2. "Metrics" tab shows:
   - CPU usage
   - Memory usage
   - Request rate

### Health Endpoint

```bash
# Check health
curl https://your-app.railway.app/health

# Should return:
# {
#   "status": "healthy",
#   "ws_age_seconds": < 60,
#   "quote_age_seconds": < 60
# }
```

**Red flags:**
- `status: "unhealthy"`
- `ws_age_seconds > 60` (WebSocket disconnected)
- `quote_age_seconds > 60` (Maker engine stopped)
- 503 error (bot crashed)

---

## Security Checklist

Before going live:

- [ ] API keys stored as environment variables (not in code)
- [ ] Config file doesn't contain secrets (use env vars)
- [ ] Git repository doesn't have `.env` files committed
- [ ] Health endpoint accessible but not exposing sensitive data
- [ ] Firewall configured (if self-hosting)
- [ ] Logs don't contain API keys

---

## Testing After Deployment

```bash
# 1. Check health
curl https://your-app-url.com/health

# 2. Check metrics
curl https://your-app-url.com/metrics

# 3. View logs (platform-specific)
# Railway: Dashboard → Logs
# DigitalOcean: App → Runtime Logs
# AWS: SSH in → docker-compose logs -f
```

---

## Troubleshooting

### Build Fails

- Check Railway logs for errors
- Verify Dockerfile is correct
- Make sure all files are in GitHub

### Health Check Failing

- Telemetry disabled → Enable it in config
- No heartbeats → Check if WS/maker is running
- Port not exposed → Check firewall/routing

### Container Crashes

- Check logs for Python exceptions
- Verify config.yaml is valid
- Check if out of memory (platform metrics)
- Restart service

### High Resource Usage

- Lower log level (INFO → WARNING)
- Disable unnecessary features
- Reduce replay speed if testing

---

## Post-Deployment Checklist

- [ ] Health endpoint responds
- [ ] Metrics endpoint accessible
- [ ] Logs show normal operation
- [ ] Alerts configured (if using)
- [ ] Monitoring set up
- [ ] API keys working (if using live trading)
- [ ] Discord alerts working (if configured)

---

## Pre-Live Trading Checklist

Before enabling live trading:

- [ ] Test with `maker.dry_run: true` for 24-48 hours
- [ ] Monitor logs closely
- [ ] Verify everything works correctly
- [ ] Set up monitoring and alerts
- [ ] Only then: Set `maker.dry_run: false` or `MAKER_DRY_RUN=false`

---

## Need Help?

1. Check logs first (always start here!)
2. Verify config is correct
3. Test locally to isolate issues
4. Check platform status pages
5. Review this guide for common issues

---

**Good luck with your deployment!** 🚀
