#!/bin/bash
# Quick health check script for lighter-bot

URL="${1:-https://lighter-bot-production.up.railway.app/health}"

echo "🔍 Checking bot health at: $URL"
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" "$URL")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ ERROR: HTTP $HTTP_CODE"
    echo "$BODY"
    exit 1
fi

# Parse JSON (basic, requires jq for full parsing)
if command -v jq &> /dev/null; then
    STATUS=$(echo "$BODY" | jq -r '.status')
    WS_AGE=$(echo "$BODY" | jq -r '.ws_age_seconds')
    QUOTE_AGE=$(echo "$BODY" | jq -r '.quote_age_seconds')

    echo "Status: $STATUS"
    echo "WebSocket age: ${WS_AGE}s"
    echo "Quote age: ${QUOTE_AGE}s"
    echo ""

    if [ "$STATUS" = "healthy" ] && (( $(echo "$WS_AGE < 60" | bc -l) )) && (( $(echo "$QUOTE_AGE < 60" | bc -l) )); then
        echo "✅ Bot is healthy!"
        exit 0
    else
        echo "⚠️  Bot may have issues:"
        [ "$STATUS" != "healthy" ] && echo "  - Status is not healthy"
        (( $(echo "$WS_AGE >= 60" | bc -l) )) && echo "  - WebSocket stale (${WS_AGE}s)"
        (( $(echo "$QUOTE_AGE >= 60" | bc -l) )) && echo "  - Quotes stale (${QUOTE_AGE}s)"
        exit 1
    fi
else
    # Fallback without jq
    if echo "$BODY" | grep -q '"status":"healthy"'; then
        echo "✅ Bot appears healthy (install jq for detailed check)"
        echo "$BODY"
        exit 0
    else
        echo "❌ Bot may be unhealthy"
        echo "$BODY"
        exit 1
    fi
fi

