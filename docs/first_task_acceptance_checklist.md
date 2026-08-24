# First Task Acceptance Checklist

Use this checklist to validate the first setup before presenting it as final to
the client.

## TradingView Compile

- Paste `pine/geo_p_momentum_strategy.pine` into TradingView Pine Editor.
- Confirm it is Pine Script v6 and compiles without warnings.
- Add it to the same symbol/timeframe used for review.
- Paste `pine/geo_p_momentum.pine` only if the client wants signal-only alerts.
- Use the signal-only indicator when validating the screenshot examples because it does not suppress labels with stop/target checks.
- Paste `pine/elliott_wave_notes.pine` separately when validating the Elliott Wave notes overlay.
- Keep `Engine mode = Candidate State (V4 Full Cycle)` for V4 validation.
- Confirm it locks Point 0 and each supported Wave 1-5 label only after the
  relevant parent-state gate passes, keeps other raw pivots developing or
  alternate, and releases an unfinished count after a hard Point-0 break.
- Use `Legacy fixed cycle` only to compare with old screenshots; it is not an
  acceptance mode for the new manual.

## Matching Settings

- Use the same symbol and chart timeframe.
- Keep `Timeframe mapping = PDF Auto` when validating the supplied 15m examples.
- For a 15m execution chart, confirm the script resolves Tide to `240` / 4H and Wave to `60` / 1H.
- In Manual mode, use the same Tide timeframe and Wave timeframe in both
  environments, and keep both equal to or higher than the execution chart.
- Keep `Signal strength` identical in Pine and Python.
- Keep `Required Better rows` identical in Pine and Python.
- Keep all indicator lengths and thresholds identical.
- Keep `Plot BUY/SELL 1 candle earlier` off during parity checks; it only shifts the visible marker.

## Screenshot Case Review

- Case 1 remains the full PDF setup check.
- Case 2 and Case 3 are covered by the Line #2 MTF refinement: Tide 4H BBUC
  plus TI uptick, and both Tide 4H RSI and Wave 1H RSI strictly above 50.
- If a marked case is still one candle late visually, test the display-only
  `Plot BUY/SELL 1 candle earlier` setting separately from parity checks.

## Python Backtest

- Install Python 3.10+ and dependencies from `requirements.txt`.
- Export the same OHLCV candles used in TradingView.
- Run `python/geo_p_momentum.py` against that CSV.
- Compare `buy_signal`, `sell_signal`, stop, and target-1 values to the Pine strategy.
- Run `compute_elliott_waves` on the same candles when validating raw pivots,
  locked `0-5` labels, parent state, reason code, Fib evidence, alternates, and
  controlled recounts.
- Verify the degree source and 144-day context first, then validate Wave 2/4
  correction completion, Wave 3 subtype, Wave 5 subtype, oscillator/divergence
  mode, and pivot sensitivity against the client chart.

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
same signal candles on identical OHLCV data. Elliott Wave milestone-2 code and
local regression coverage are complete. Its milestone-3 acceptance still
requires TradingView compilation/replay, candle-for-candle parity, performance
checks, client-confirmed locked counts, and backtesting on agreed datasets.
