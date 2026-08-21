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
- Keep `Engine mode = Candidate State (Phase 1)` for developer-manual validation.
- Confirm it locks only Point 0/Wave 1, shows degree/evidence/reason state, keeps
  later raw pivots as developing or alternate, and releases the count after a
  hard Point-0 break.
- Use `Legacy fixed cycle` only to compare with old screenshots; it is not an
  acceptance mode for the new manual.

## Matching Settings

- Use the same symbol and chart timeframe.
- Keep `Timeframe mapping = PDF Auto` when validating the supplied 15m examples.
- For a 15m execution chart, confirm the script resolves Tide to `240` / 4H and Wave to `60` / 1H.
- In Manual mode, use the same Tide timeframe and Wave timeframe in both environments.
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
  locked `0/1` labels, state, reason code, degree progress, alternates, and
  controlled recounts.
- For Phase 1, verify engine mode, degree preset/source, 144-day context,
  61.8% progress, 5/9/13/17/21 internal count, oscillator mode, direction,
  ATR filter, and pivot sensitivity against the client chart.

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
same signal candles on identical OHLCV data. Elliott Wave Phase 1 can be called
accepted only after its regression tests pass, Pine compiles in TradingView,
and the client confirms the same locked base/invalidation behavior on identical
market data. Later wave/correction modules remain outside that acceptance.
