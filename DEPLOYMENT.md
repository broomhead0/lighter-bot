# Deployment Guide - Step by Step

This guide will walk you through deploying your lighter-bot to production. We'll go step by step!

## 🎯 Pre-Deployment Checklist

Before deploying, let's make sure everything is ready:

### ✅ What You'll Need

1. **Cloud Provider Account** (choose one):
   - AWS (Amazon Web Services) - Free tier available
   - Google Cloud Platform (GCP) - Free tier available
   - DigitalOcean - Simple, affordable ($5-10/month)
   - Railway/Render - Super easy, free tier available

2. **API Keys** (if using live trading):
   - Lighter.xyz API key
   - Lighter.xyz API secret
   - Discord webhook URL (for alerts)

3. **Domain** (optional):
   - For easier access to health endpoints
   - Not required for basic deployment

### ✅ Pre-Flight Checks

Run these locally first:

```bash
# 1. Test locally without Docker
source .venv/bin/activate
export PYTHONPATH=.
python -m core.main
# (Ctrl+C to stop after a few seconds)

# 2. Test with Docker
docker-compose up -d
sleep 5
curl http://localhost:9100/health
docker-compose down

# 3. Verify config
cat config.yaml | grep -E "(enabled|url|key)"
```

## 🚀 Deployment Options (Pick One)

### Option 1: Railway (Easiest - Recommended for Beginners)

**Why Railway?**
- Free tier available
- Automatic deployments from GitHub
- Built-in Docker support
- Easy environment variables
- HTTPS included

**Steps:**

1. **Sign up**: Go to https://railway.app and sign up with GitHub

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select your `lighter-bot` repository

3. **Configure Environment Variables**:
   ```
   PYTHONPATH=/app
   PYTHONUNBUFFERED=1
   LOG_LEVEL=INFO
   WS_URL=wss://mainnet.zklighter.elliot.ai/stream/market_stats:all
   ```

4. **Set up Secrets** (optional, for production):
   - Add to Railway's environment variables:
     ```
     API_KEY=your_lighter_api_key
     API_SECRET=your_lighter_api_secret
     DISCORD_WEBHOOK=your_discord_webhook_url
     ```

5. **Deploy**:
   - Railway auto-detects Docker
   - It will build and deploy automatically
   - Watch the logs in Railway dashboard

6. **Get Your URL**:
   - Railway gives you a public URL
   - Access health: `https://your-app.railway.app/health`

### Option 2: DigitalOcean App Platform

**Why DigitalOcean?**
- Simple pricing ($5/month minimum)
- Good documentation
- Reliable

**Steps:**

1. **Sign up**: https://www.digitalocean.com

2. **Create App**:
   - Go to "Apps" → "Create App"
   - Connect GitHub repository
   - Select your `lighter-bot` repo

3. **Configure**:
   - **Build Command**: (leave empty, Docker handles it)
   - **Run Command**: `python -m core.main`
   - **Port**: `9100`

4. **Environment Variables**:
   - Add all from Railway example above

5. **Deploy**:
   - Click "Create Resources"
   - Wait for deployment (~5-10 minutes)

### Option 3: AWS EC2 (More Control)

**Why AWS?**
- Most flexible
- Free tier for 12 months
- Industry standard

**Steps:**

1. **Launch EC2 Instance**:
   - Go to AWS Console → EC2
   - Click "Launch Instance"
   - Choose: Ubuntu 22.04 LTS (free tier)
   - Instance type: t2.micro (free tier)
   - Create/select key pair (download .pem file)
   - Configure security group:
     - Allow SSH (port 22) from your IP
     - Allow HTTP (port 9100) from anywhere (or your IP)
   - Launch instance

2. **Connect to Instance**:
   ```bash
   # On your Mac
   chmod 400 your-key.pem
   ssh -i your-key.pem ubuntu@YOUR_EC2_IP
   ```

3. **Install Docker on EC2**:
   ```bash
   # On the EC2 instance
   sudo apt update
   sudo apt install -y docker.io docker-compose
   sudo usermod -aG docker ubuntu
   # Log out and back in
   exit
   # SSH back in
   ```

4. **Clone Your Repo**:
   ```bash
   # On EC2
   git clone https://github.com/YOUR_USERNAME/lighter-bot.git
   cd lighter-bot
   ```

5. **Configure**:
   ```bash
   # Edit config with your secrets
   nano config.yaml
   # Set: replay.enabled: false
   # Set: telemetry.enabled: true
   # Add API keys if needed
   ```

6. **Deploy**:
   ```bash
   docker-compose up -d
   ```

7. **Check**:
   ```bash
   curl http://localhost:9100/health
   ```

### Option 4: Render (Super Simple)

**Why Render?**
- Free tier available
- Very easy setup
- Auto-deploys from GitHub

**Steps:**

1. **Sign up**: https://render.com

2. **New Web Service**:
   - Connect GitHub
   - Select repository
   - **Environment**: Docker
   - **Build Command**: (auto-detected)
   - **Start Command**: `python -m core.main`

3. **Environment Variables**: (same as Railway)

4. **Deploy**: Click "Create Web Service"

## 📋 Production Configuration

Before deploying, update your `config.yaml` for production:

### Required Changes

```yaml
# Disable replay mode
replay:
  enabled: false

# Enable telemetry
telemetry:
  enabled: true
  port: 9100

# Disable chaos (unless testing)
chaos:
  enabled: false

# Configure alerts (if you have Discord webhook)
alerts:
  enabled: true
  discord_webhook_url: ${DISCORD_WEBHOOK}  # Use env var

# Set proper log level
app:
  log_level: INFO  # or WARNING for less noise
```

### Using Environment Variables

Instead of hardcoding secrets, use environment variables:

```yaml
# In config.yaml
api:
  base_url: ${API_BASE_URL}
  key: ${API_KEY}
  secret: ${API_SECRET}

alerts:
  discord_webhook_url: ${DISCORD_WEBHOOK}
```

Then set them in your deployment platform.

## 🔒 Security Checklist

Before going live:

- [ ] **API keys** stored as environment variables (not in code)
- [ ] **Config file** doesn't contain secrets (use env vars)
- [ ] **Git repository** doesn't have `.env` files committed
- [ ] **Health endpoint** is accessible but not exposing sensitive data
- [ ] **Firewall** configured (if self-hosting)
- [ ] **Logs** don't contain API keys

## 🧪 Testing After Deployment

Once deployed:

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

## 📊 Monitoring

### What to Monitor

1. **Health Endpoint**:
   - Set up uptime monitoring (UptimeRobot, Pingdom)
   - Check every 5 minutes
   - Alert if unhealthy

2. **Logs**:
   - Watch for errors
   - Check for kill-switch triggers
   - Monitor cancel rates

3. **Metrics**:
   - WS heartbeat age (should be < 60s)
   - Quote heartbeat age (should be < 60s)
   - Uptime

### Setting Up Alerts

**UptimeRobot** (free):
1. Sign up at https://uptimerobot.com
2. Add monitor:
   - Type: HTTP(s)
   - URL: `https://your-app-url.com/health`
   - Interval: 5 minutes
3. Add alert contacts (email/SMS)

## 🐛 Troubleshooting

### Container Won't Start

**Check logs:**
```bash
# Platform-specific
railway logs
# or
docker-compose logs
```

**Common issues:**
- Missing environment variables
- Port conflicts
- Config file errors

### Health Check Failing

**Possible causes:**
- Telemetry disabled → Enable it
- No heartbeats → Check if WS/maker is running
- Port not exposed → Check firewall/routing

### High Resource Usage

**If using free tier:**
- Lower log level (INFO → WARNING)
- Disable unnecessary features
- Reduce replay speed if testing

## 📝 Post-Deployment Checklist

After deployment:

- [ ] Health endpoint responds
- [ ] Metrics endpoint accessible
- [ ] Logs show normal operation
- [ ] Alerts configured (if using)
- [ ] Monitoring set up
- [ ] API keys working (if using live trading)
- [ ] Discord alerts working (if configured)

## 🎓 Next Steps

1. **Monitor for 24-48 hours** to ensure stability
2. **Set up log aggregation** (optional but recommended)
3. **Configure backup** of config and logs
4. **Document your setup** for future reference
5. **Set up auto-scaling** (if needed later)

## 💡 Tips for Beginners

1. **Start small**: Test on free tier first
2. **Monitor closely**: Watch logs for first few hours
3. **Keep config simple**: Don't enable all features at once
4. **Use dry-run**: Test with `maker.dry_run: true` first
5. **Backup config**: Keep production config in secure location
6. **Document everything**: Write down what you did

## 🆘 Need Help?

If something goes wrong:

1. **Check logs** first (always start here!)
2. **Verify config** is correct
3. **Test locally** to isolate issues
4. **Check platform status** (Railway/DigitalOcean status pages)
5. **Review this guide** for common issues

## 🎉 Congratulations!

Once deployed and running, you'll have:
- ✅ Production-ready bot
- ✅ Health monitoring
- ✅ Automated deployment
- ✅ Professional setup

Good luck with your deployment! 🚀

