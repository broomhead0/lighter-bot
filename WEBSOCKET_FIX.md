# WebSocket URL Fix

## Issue
The WebSocket URL was incorrect, causing 404 errors:
- ❌ Wrong: `wss://mainnet.zklighter.elliot.ai/stream/market_stats:all`
- ✅ Correct: `wss://mainnet.zklighter.elliot.ai/stream`

## Fix Applied
Updated `config.yaml` with the correct URL from [Lighter API docs](https://apidocs.lighter.xyz/docs/websocket-reference).

## Update Railway

**You need to update the Railway environment variable:**

1. Go to Railway dashboard → Your service
2. Click "Variables" tab
3. Find `WS_URL`
4. Update it to: `wss://mainnet.zklighter.elliot.ai/stream`
5. Save (Railway will auto-redeploy)

Or wait for the next deployment - the config.yaml fix will be picked up automatically.

## Verify Fix

After updating, check logs for:
- ✅ `[listener] WS connected` (no more 404 errors)
- ✅ `[router] mid updated` messages (real market data)
- ✅ Health endpoint shows low `ws_age_seconds`

## Reference
- Lighter WebSocket docs: https://apidocs.lighter.xyz/docs/websocket-reference
- Lighter main docs: https://docs.lighter.xyz/

