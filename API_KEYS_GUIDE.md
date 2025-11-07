# API Keys & Discord Webhook Guide

## 🎯 Quick Answer

**For initial deployment: You DON'T need any of these!**

The bot will work perfectly fine without them:
- ✅ **API Keys**: Not needed (bot runs in dry-run mode)
- ✅ **Discord Webhook**: Not needed (alerts just log to console)

**You only need them later when:**
- Going live with real trading (API keys)
- Want Discord notifications (webhook)

---

## 📋 What Each One Does

### 1. API_KEY & API_SECRET (Lighter.xyz API)

**What it's for:**
- Placing actual orders on Lighter.xyz
- Canceling orders
- Getting account info

**Do you need it now?**
- ❌ **NO** - The bot is in `dry_run: true` mode
- ✅ **YES** - Only when you want to trade with real money

**What happens without it:**
- Bot runs normally
- Quotes are calculated and logged
- Orders are simulated (not actually placed)
- Logs show: `[maker] DRY-RUN: would place bid=... ask=...`

**How to get it:**
1. Go to Lighter.xyz platform
2. Log in to your account
3. Navigate to API/Settings section
4. Generate API key and secret
5. Copy both values

**When to add it:**
- After testing the bot for 24-48 hours
- When you're confident it's working correctly
- When ready to switch `maker.dry_run: false`

---

### 2. DISCORD_WEBHOOK (Discord Notifications)

**What it's for:**
- Sending alerts to a Discord channel
- Notifications when bot starts/stops
- Error alerts
- Kill-switch notifications

**Do you need it now?**
- ❌ **NO** - Alerts just log to console without it
- ✅ **YES** - Only if you want Discord notifications

**What happens without it:**
- Bot runs normally
- Alerts are logged to console/logs instead
- No Discord messages sent

**How to get it:**
1. Open Discord
2. Go to your server (or create one)
3. Go to **Server Settings** → **Integrations** → **Webhooks**
4. Click **New Webhook**
5. Name it (e.g., "Lighter Bot Alerts")
6. Choose a channel for alerts
7. Click **Copy Webhook URL**
8. That's your webhook URL!

**Example webhook URL:**
```
https://discord.com/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz
```

**When to add it:**
- Anytime (optional)
- Recommended for production monitoring
- Helps you know if bot crashes or has issues

---

## 🚀 Deployment Without Keys

**You can deploy right now with just:**

```
PYTHONPATH = /app
PYTHONUNBUFFERED = 1
LOG_LEVEL = INFO
WS_URL = wss://mainnet.zklighter.elliot.ai/stream/market_stats:all
```

That's it! The bot will:
- ✅ Connect to WebSocket
- ✅ Calculate quotes
- ✅ Run in safe dry-run mode
- ✅ Log everything (no Discord needed)

---

## 📝 Adding Keys Later

### Adding API Keys (when ready for live trading):

1. **Get your keys** from Lighter.xyz
2. **In Railway**: Go to Variables → Add:
   ```
   API_KEY = your_key_here
   API_SECRET = your_secret_here
   ```
3. **Update config** (or set via env var):
   ```yaml
   api:
     key: ${API_KEY}
     secret: ${API_SECRET}
   ```
4. **Change dry-run mode**:
   ```yaml
   maker:
     dry_run: false  # ⚠️ Only after thorough testing!
   ```

### Adding Discord Webhook (anytime):

1. **Create webhook** in Discord (see steps above)
2. **In Railway**: Go to Variables → Add:
   ```
   DISCORD_WEBHOOK = https://discord.com/api/webhooks/...
   ```
3. **Update config** (or set via env var):
   ```yaml
   alerts:
     discord_webhook_url: ${DISCORD_WEBHOOK}
   ```

---

## 🔒 Security Tips

1. **Never commit keys to git** - Always use environment variables
2. **Use Railway's Variables tab** - They're encrypted
3. **Rotate keys periodically** - For security
4. **Test with dry-run first** - Always!

---

## ✅ Summary

**For initial deployment:**
- ❌ API keys: Not needed
- ❌ Discord webhook: Not needed

**Required environment variables:**
- ✅ PYTHONPATH
- ✅ PYTHONUNBUFFERED
- ✅ LOG_LEVEL
- ✅ WS_URL

**Add later when ready:**
- API keys → When going live
- Discord webhook → When you want notifications

You're good to deploy! 🚀

