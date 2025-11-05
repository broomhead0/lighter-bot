# Pre-Deployment Checklist

Run through this checklist before deploying to production!

## 🔍 Local Testing

```bash
# 1. Test without Docker
source .venv/bin/activate
export PYTHONPATH=.
python -m core.main
# Let it run for 30 seconds, then Ctrl+C
# Check for errors in output

# 2. Test with Docker
docker-compose up -d
sleep 10
curl http://localhost:9100/health
docker-compose logs | tail -50
docker-compose down

# 3. Test replay mode
python scripts/generate_test_replay_data.py logs/ws_raw.jsonl 10
# Edit config.yaml: replay.enabled: true
docker-compose up -d
# Wait for completion
docker-compose logs | grep "REPLAY SUMMARY"
docker-compose down
```

## 📝 Configuration Review

### Check These Settings:

- [ ] **Replay mode**: `enabled: false` (for production)
- [ ] **Chaos injector**: `enabled: false` (for production)
- [ ] **Telemetry**: `enabled: true` (required for health checks)
- [ ] **Log level**: `INFO` or `WARNING` (not DEBUG)
- [ ] **Maker dry_run**: `false` (if going live) OR `true` (if testing)
- [ ] **API keys**: Use environment variables, not hardcoded
- [ ] **Discord webhook**: Set if you want alerts

### Security:

- [ ] No secrets in `config.yaml` (use env vars)
- [ ] `.env` file in `.gitignore`
- [ ] No API keys committed to git
- [ ] Secrets stored securely in deployment platform

## 🐳 Docker Verification

```bash
# Build and test
docker build -t lighter-bot:test .
docker run --rm -it lighter-bot:test
# Should start without errors
# Ctrl+C to stop
```

## 📦 Repository Check

- [ ] Code committed to git
- [ ] `.env` not in repository
- [ ] `config.yaml` doesn't contain secrets
- [ ] `.gitignore` includes sensitive files

## 🚀 Deployment Platform Setup

### If Using Railway/Render/DigitalOcean:

- [ ] Account created
- [ ] GitHub repository connected
- [ ] Environment variables ready to add
- [ ] Billing/payment method set up (if needed)

### Environment Variables to Prepare:

```
PYTHONPATH=/app
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
WS_URL=wss://mainnet.zklighter.elliot.ai/stream/market_stats:all
API_KEY=(your key)
API_SECRET=(your secret)
DISCORD_WEBHOOK=(your webhook)
```

## 📊 Monitoring Setup

- [ ] Uptime monitoring service account created (UptimeRobot, etc.)
- [ ] Health endpoint URL noted
- [ ] Alert email/phone configured

## ✅ Final Checks

Before clicking "Deploy":

1. **Test locally** one more time
2. **Review config** for production settings
3. **Backup current config** (if you have one)
4. **Have deployment guide open** (DEPLOYMENT.md)
5. **Monitor logs** during first deployment

## 🎯 Ready to Deploy?

If everything above is checked, you're ready!

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step deployment instructions.

