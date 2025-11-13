# Volatility Comparison & Threshold Validation (2025-11-13)

## Current State

**Time:** 19:55 PT (2025-11-13)

### External SOL Volatility (Binance)
- **Last 60 minutes:** 6.18 bps
- **Last 15 minutes:** 6.39 bps
- **Source:** Binance SOL/USDT 1m candles

### Internal Bot Volatility
- **Current EMA:** 1.96 bps
- **Method:** 45-second half-life EMA of absolute price changes
- **Status:** Low-volatility pause ACTIVE (1.96 < 3.0 bps threshold)

### Thresholds
- **Low-vol pause:** 3.0 bps (pause maker when vol < threshold)
- **Regime switch:** 6.0 bps (switch aggressive/defensive)
- **High-vol pause:** 30.0 bps (pause maker when vol > threshold)

## Finding: Significant Discrepancy

**External market volatility (6.18-6.39 bps) suggests:**
- Normal/active trading conditions
- Should be in aggressive regime (vol >= 6.0 bps)
- Maker should be active, not paused

**Internal bot volatility (1.96 bps) indicates:**
- Very low volatility
- Low-vol pause is active
- Maker is paused (preventing trading)

## Analysis

### Possible Causes

1. **EMA Lag**: The 45-second half-life EMA might be responding too slowly to recent price movements
   - External vol measures last 60 minutes of activity
   - Internal EMA heavily weights recent observations but may miss brief spikes

2. **Calculation Method Difference**:
   - External: Average absolute return over 60 1-minute candles
   - Internal: EMA of absolute price changes with 45s half-life
   - These measure different things: external is backward-looking average, internal is exponential moving average

3. **Recent Quiet Period**: The bot may have been paused during a brief quiet period, missing the overall higher volatility

### Impact

- **Maker is paused** when market conditions suggest it should be active
- **Missing trading opportunities** during normal volatility (6-7 bps)
- **Being too conservative** - market volatility is above regime switch threshold (6.0 bps)

## Recommendations

### 1. Adjust Internal Volatility Calculation
- Consider using a shorter half-life (e.g., 30s instead of 45s) for faster response
- Or use a hybrid: shorter EMA for pause decisions, longer for regime switching
- Or add a "recent spike detection" to override low EMA when recent movements are high

### 2. Re-evaluate Low-Vol Pause Threshold
- Current threshold: 3.0 bps
- External market at 6.18 bps but internal at 1.96 bps suggests:
  - Threshold might be too conservative
  - Or internal calculation needs adjustment

### 3. Add External Volatility Check
- Fetch external SOL volatility periodically (every 5-10 minutes)
- Use as a "sanity check" to override internal EMA if significantly different
- Example: If external vol > 6.0 bps but internal < 3.0 bps, use external for pause decisions

### 4. Immediate Actions
- **Consider raising low-vol pause threshold** from 3.0 to 4.0-5.0 bps
- **Or add minimum trading threshold** that considers external volatility
- **Monitor the discrepancy** over next 24 hours to see if it's consistent

## Next Steps

1. ✅ Compare internal vs external volatility (DONE)
2. ⏳ Run full regime analysis with recent data
3. ⏳ Decide on threshold adjustments
4. ⏳ Implement external volatility check (optional)
5. ⏳ Monitor and validate changes

## Related Findings

From previous analysis (2025-11-12):
- **NY Market Hours (high vol)**: Better performance, fewer large crosses
- **Overnight (low vol)**: Worse performance, more large crosses
- **Volatility correlation**: Mid/high volatility drove negative PnL in past data

This current finding suggests we may be **too conservative** - pausing during what external data suggests are normal trading conditions.

