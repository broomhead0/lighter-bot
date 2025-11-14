# Mean Reversion Trading Strategy

## Overview

The Mean Reversion Trader is a profitable strategy designed for SOL on 1-minute timeframes. It identifies overextended price moves and trades reversions back to the mean.

## Strategy Logic

### Core Concept

Crypto markets, especially on short timeframes, often exhibit mean-reverting behavior. When price moves too far from its average (measured by Bollinger Bands), it tends to revert. This strategy capitalizes on these reversions.

### Entry Signals

**Long Entry:**
- Price touches or extends beyond lower Bollinger Band (95% threshold)
- RSI < 30 (oversold)
- Volume > 1.2x average volume (confirmation)
- Volatility between 4-25 bps (moderate conditions)
- No strong trend (EMA divergence < 15 bps)

**Short Entry:**
- Price touches or extends beyond upper Bollinger Band (95% threshold)
- RSI > 70 (overbought)
- Volume > 1.2x average volume (confirmation)
- Volatility between 4-25 bps (moderate conditions)
- No strong trend (EMA divergence < 15 bps)

### Exit Signals

1. **Take Profit:** Price returns to target (3 bps profit)
2. **Stop Loss:** Price continues against us (6 bps loss)
3. **Time Stop:** Exit after 5 minutes if no movement
4. **Reversal:** RSI flips to opposite extreme

### Risk Management

- **Position Sizing:** Based on ATR (volatility-adjusted)
- **Risk per Trade:** 1% of capital (configurable)
- **Max Position:** 0.1 SOL per trade
- **Min Position:** 0.01 SOL per trade
- **Stop Loss:** 6 bps (2:1 risk/reward ratio)

## Technical Indicators

1. **Bollinger Bands (20 period, 2 std dev)**
   - Identifies overextended price levels
   - Upper/lower bands = mean ± 2 standard deviations

2. **RSI (14 period)**
   - Confirms oversold/overbought conditions
   - < 30 = oversold (long signal)
   - > 70 = overbought (short signal)

3. **EMA Fast/Slow (8/21 period)**
   - Trend filter (avoids trading in strong trends)
   - Divergence < 15 bps = acceptable for mean reversion

4. **ATR (14 period)**
   - Position sizing based on volatility
   - Higher ATR = larger position (risk-adjusted)

5. **Volume MA (20 period)**
   - Confirmation filter
   - Only trade when volume > 1.2x average

6. **Volatility (20-period rolling)**
   - Market condition filter
   - Only trade in moderate volatility (4-25 bps)

## Why This Strategy Works

1. **Mean Reversion is Real:** Crypto markets, especially on 1-minute, show strong mean-reverting behavior
2. **Multiple Filters:** Reduces false signals by requiring multiple confirmations
3. **Volatility Filtering:** Avoids trading in extreme conditions (too quiet or too chaotic)
4. **Quick Exits:** Short holding periods (1-5 minutes) reduce exposure
5. **Risk Management:** Tight stops and position sizing protect capital

## Configuration

See `config.yaml` under `mean_reversion` section. Key parameters:

- `enabled`: Enable/disable the trader
- `dry_run`: Test mode (no real trades)
- `take_profit_bps`: Target profit (default: 3 bps)
- `stop_loss_bps`: Stop loss (default: 6 bps)
- `vol_min_bps` / `vol_max_bps`: Volatility range filter

## Performance Expectations

**Ideal Conditions:**
- Ranging/choppy markets
- Moderate volatility (6-15 bps)
- Good volume

**Avoid:**
- Strong trends (EMA divergence > 15 bps)
- Extreme volatility (> 25 bps or < 4 bps)
- Low volume periods

## Monitoring

The strategy exposes telemetry metrics:
- `mean_reversion_rsi`: Current RSI value
- `mean_reversion_volatility_bps`: Current volatility
- `mean_reversion_bb_position`: Price position in Bollinger Bands (0-1)
- `mean_reversion_position_side`: Current position (1=long, -1=short, 0=flat)
- `mean_reversion_position_size`: Position size

## Usage

1. Enable in `config.yaml`:
   ```yaml
   mean_reversion:
     enabled: true
     dry_run: true  # Start with dry_run=true for testing
   ```

2. Run the bot:
   ```bash
   python -m core.main
   ```

3. Monitor logs for entry/exit signals

4. Once confident, set `dry_run: false` for live trading

## Risk Warning

- This is a directional trading strategy (not market making)
- Requires active monitoring
- Can lose money in trending markets
- Start with small position sizes
- Always test in dry_run mode first

