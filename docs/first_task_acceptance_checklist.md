# First Task Acceptance Checklist

Use this checklist to validate the first setup before presenting it as final to
the client.

## TradingView Compile

- Paste `pine/geo_p_momentum_strategy.pine` into TradingView Pine Editor.
- Confirm it is Pine Script v6 and compiles without warnings.
- Add it to the same symbol/timeframe used for review.
- Paste `pine/geo_p_momentum.pine` only if the client wants signal-only alerts.
- Use the signal-only indicator when validating the screenshot examples because it does not suppress labels with stop/target checks.

## Matching Settings

- Use the same symbol and chart timeframe.
- Use the same Tide timeframe.
- Keep `Signal strength` identical in Pine and Python.
- Keep `Required Better rows` identical in Pine and Python.
- Keep all indicator lengths and thresholds identical.
- Keep `Plot BUY/SELL 1 candle earlier` off during parity checks; it only shifts the visible marker.

## Python Backtest

- Install Python 3.10+ and dependencies from `requirements.txt`.
- Export the same OHLCV candles used in TradingView.
- Run `python/geo_p_momentum.py` against that CSV.
- Compare `buy_signal`, `sell_signal`, stop, and target-1 values to the Pine strategy.

## Client Confirmation

Ask the client to confirm exact formulas for these PDF abbreviations:

- `TI`
- `ADX Ungli`
- exact manual trendline rule, if their drawing method is proprietary
- exact target rule, if major support/resistance or Fibonacci selection has custom rules

Current ADX Ungli interpretation from the TradingView screenshots: ADX hooks
upward while +DI/-DI separates in the signal direction.

Do not ask for `SOBBO/SOBBD` or `TMG/TMJ` unless the client later reverses the
latest instruction; those terms are intentionally ignored in this version.

The first setup can be called fully verified after Pine and Python produce the
same signal candles on identical OHLCV data.
