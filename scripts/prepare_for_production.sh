#!/bin/bash
# Helper script to prepare config for production deployment

set -e

echo "🔧 Preparing lighter-bot for production deployment..."
echo ""

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "❌ Error: config.yaml not found!"
    exit 1
fi

# Backup current config
BACKUP_FILE="config.yaml.backup.$(date +%Y%m%d_%H%M%S)"
cp config.yaml "$BACKUP_FILE"
echo "✅ Backed up current config to: $BACKUP_FILE"
echo ""

# Create production-safe config suggestions
echo "📝 Production Configuration Recommendations:"
echo ""
echo "1. Replay mode should be DISABLED:"
echo "   replay.enabled: false"
echo ""
echo "2. Chaos injector should be DISABLED:"
echo "   chaos.enabled: false"
echo ""
echo "3. Telemetry should be ENABLED:"
echo "   telemetry.enabled: true"
echo ""
echo "4. Log level should be INFO or WARNING:"
echo "   app.log_level: INFO"
echo ""
echo "5. Maker dry_run - set to false for live trading:"
echo "   maker.dry_run: false  # ONLY after testing!"
echo ""
echo "6. Use environment variables for secrets:"
echo "   api.key: \${API_KEY}"
echo "   api.secret: \${API_SECRET}"
echo "   alerts.discord_webhook_url: \${DISCORD_WEBHOOK}"
echo ""

# Check current settings
echo "🔍 Current Configuration Status:"
echo ""

REPLAY_ENABLED=$(grep -A 1 "^replay:" config.yaml | grep "enabled:" | awk '{print $2}' || echo "not found")
CHAOS_ENABLED=$(grep -A 1 "^chaos:" config.yaml | grep "enabled:" | awk '{print $2}' || echo "not found")
TELEMETRY_ENABLED=$(grep -A 1 "^telemetry:" config.yaml | grep "enabled:" | awk '{print $2}' || echo "not found")
LOG_LEVEL=$(grep -A 1 "^app:" config.yaml | grep "log_level:" | awk '{print $2}' || echo "not found")

echo "  Replay: $REPLAY_ENABLED"
if [ "$REPLAY_ENABLED" = "true" ]; then
    echo "    ⚠️  WARNING: Replay should be false for production"
fi

echo "  Chaos: $CHAOS_ENABLED"
if [ "$CHAOS_ENABLED" = "true" ]; then
    echo "    ⚠️  WARNING: Chaos should be false for production"
fi

echo "  Telemetry: $TELEMETRY_ENABLED"
if [ "$TELEMETRY_ENABLED" = "false" ]; then
    echo "    ⚠️  WARNING: Telemetry should be true for production (health checks need it)"
fi

echo "  Log Level: $LOG_LEVEL"
if [ "$LOG_LEVEL" = "DEBUG" ]; then
    echo "    ⚠️  WARNING: DEBUG logging is verbose, consider INFO for production"
fi

echo ""
echo "📦 Git Status Check:"
echo ""

# Check for sensitive files
if git ls-files | grep -q "\.env$"; then
    echo "  ⚠️  WARNING: .env file is tracked in git (should be in .gitignore)"
fi

if grep -q "key:.*[a-zA-Z0-9]\{20,\}" config.yaml; then
    echo "  ⚠️  WARNING: Possible API keys found in config.yaml (use env vars instead)"
fi

echo ""
echo "✅ Preparation complete!"
echo ""
echo "Next steps:"
echo "1. Review the warnings above"
echo "2. Update config.yaml with production settings"
echo "3. Test locally: docker-compose up -d"
echo "4. Follow DEPLOY_QUICKSTART.md for deployment"
echo ""

