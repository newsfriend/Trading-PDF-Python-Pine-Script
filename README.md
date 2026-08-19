# Trading Setup Conversion

This workspace contains the first converted setup from the supplied PDF/chart
material:

**GEO P Momentum - Momentum Trader: Bollinger Band Challenge with Trendline Break**

The implementation follows the attached PDF checklist with the latest
ignore-instruction applied, and matches the full project requirement: Pine
Script v6 for TradingView plus a Python 3.10+ module for backtesting with
matching entry/exit signals.

## Files

- `pine/geo_p_momentum_strategy.pine` - Main TradingView Pine v6 strategy with entries, exits, BUY/SELL markers, alerts, stop, and target validation.
- `pine/geo_p_momentum.pine` - Signal-only TradingView Pine v6 indicator for clients who only want BUY/SELL markers and alerts without stop/target validation hiding labels.
- `python/geo_p_momentum.py` - Matching Python signal engine and simple target-1 backtest helper.
- `python/__init__.py` - Package export.
- `docs/geo_p_momentum_pdf_rules.md` - Row-by-row extraction of the first PDF checklist.
- `docs/first_task_acceptance_checklist.md` - Compile/parity checklist for validating the first setup.
- `requirements.txt` - Minimal Python dependencies.

Only one PDF/setup is present in the workspace, so only the first setup is
implemented. The remaining 10-12 setup package can be completed as soon as the
remaining PDFs are supplied.

## Rule Mapping

The first PDF/screenshot checklist is implemented as a BUY/SELL setup.
Rows marked `Buy` or `Sell` are scored. The `Signal strength` input controls
how many of those rows must agree:

- `Fast` - mandatory PDF conditions only.
- `Balanced` - mandatory PDF conditions plus 3 of 5 Buy/Sell rows.
- `Strict PDF` - mandatory PDF conditions plus all 5 Buy/Sell rows.

The Pine files and Python module use `Balanced` by default and require zero
Better rows by default. Use `Strict PDF` when the client wants every visible
Buy/Sell row satisfied before a signal. `Required Better rows` can enforce up to
four active Better confirmations.

Per the latest client/user instruction, PDF Step 2 is ignored and
`SOBBO/SOBBD` plus `TMG/TMJ` are not used in the active signal logic.

## Buy Side

Mandatory gate:

- `Tide - BBUC OR price in upper half`
- `Tide - TI uptick`
- `Tide and Wave - RSI > 50`
- `Wave - BBUC with TLBO`

PDF Buy rows scored:

- Above-average volume for the breakout candle.
- At least two higher lows on line-chart close pivots.
- 5 EMA positive crossover with 13 EMA or 26 EMA in the last 3 bars.
- DI positive crossover.
- Directional ADX Ungli, or ADX above 15.

Better confirmations available as optional filters:

- TI above zero.
- RSI crossing above 60.
- Price above 50 EMA.
- No immediate major resistance.

## Sell Side

Mandatory gate:

- `Tide - BBDC OR price in lower half`
- `Tide - TI downtick`
- `Tide and Wave - RSI < 50`
- `Wave - BBDC with TLBD`

PDF Sell rows scored:

- Above-average volume for the breakdown candle.
- At least two lower highs on line-chart close pivots.
- 5 EMA negative crossover with 13 EMA or 26 EMA in the last 3 bars.
- DI negative crossover.
- Directional ADX Ungli, or ADX above 15.

Better confirmations available as optional filters:

- TI below zero.
- RSI crossing below 40.
- Price below 50 EMA.
- No immediate major support.

## Stop And Target

The full Pine strategy and Python backtester use the PDF stop/target wording:

- BUY stop: below the BB challenge candle or TLBO point.
- SELL stop: above the BB challenge candle or TLBD point.
- Target 1: nearest major support/resistance when available; otherwise a Fibonacci extension of the recent swing range.

## Configurable Assumptions

The PDF checklist does not give formulas for every proprietary abbreviation.
These definitions are explicit in code and can be replaced if the client gives
a glossary:

- Bollinger Bands default to `20, 2.0`.
- `BBUC` means high challenges the upper Bollinger Band.
- `BBDC` means low challenges the lower Bollinger Band.
- `TI` is implemented as `EMA(13) - EMA(26)`, with uptick/downtick checks.
- `TLBO/TLBD` use confirmed pivot trendline breaks, with a range-break fallback.
- `DI PCO/NCO` use +DI/-DI crossovers from DMI.
- `ADX Ungli` is implemented from the TradingView screenshots as an ADX upward hook while +DI/-DI spreads in the trade direction, or ADX above 15.
- PDF Step 2, `SOBBO/SOBBD`, and `TMG/TMJ` are intentionally ignored per the latest instruction.

## TradingView Screenshot Alignment

The supplied TradingView screenshots highlight the lower ADX/DMI panel before
continuation moves. The implementation interprets that visual as:

- Buy-side ADX Ungli: ADX hooks upward, +DI is above -DI, and the DI spread expands.
- Sell-side ADX Ungli: ADX hooks upward, -DI is above +DI, and the DI spread expands.
- The same rules are used in Pine and Python.

The signal-only Pine indicator plots the PDF setup signal directly; the strategy
file additionally checks valid stop/target placement before placing orders.
Both Pine files include a display option named `Plot BUY/SELL 1 candle earlier`.
This shifts only the visible chart marker one bar left. It does not move alerts,
orders, or Python signals earlier, because that would require predicting a
future confirmed candle and would repaint.

## TradingView Usage

1. Open TradingView Pine Editor.
2. Paste `pine/geo_p_momentum_strategy.pine` for the full strategy/backtest deliverable.
3. Paste `pine/geo_p_momentum.pine` instead only when the client wants signal markers and alerts without strategy orders.
4. Set `Tide timeframe` to the higher timeframe used by the client, or leave blank to use the chart timeframe.
5. Keep `Signal strength` and `Required Better rows` the same in Pine and Python when comparing signals.
6. Enable `Plot BUY/SELL 1 candle earlier` only when the client wants earlier-looking chart labels for visual review.

## Python Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Use from code:

```python
import pandas as pd
from python.geo_p_momentum import GeoPMomentumConfig, backtest_signals, compute_signals

df = pd.read_csv("xauusd_15m.csv", parse_dates=["time"]).set_index("time")
cfg = GeoPMomentumConfig(tide_timeframe="60", signal_mode="Balanced")

signals = compute_signals(df, cfg)
trades = backtest_signals(signals)

print(signals[signals["buy_signal"] | signals["sell_signal"]])
print(trades)
```

Or run as a CLI:

```bash
python python/geo_p_momentum.py xauusd_15m.csv --time-column time --tide-timeframe 60 --signal-mode Balanced --min-better-confirmations 0 --output signals.csv
```

## Parity Notes

For candle-for-candle alignment between TradingView and Python:

- Use the same OHLCV data, exchange session, timezone, and candle close timestamps.
- Use the same Tide timeframe in both environments. Python accepts TradingView-style intraday values such as `60`.
- Use the same Signal strength in both environments.
- Use the same Required Better rows / `min_better_confirmations` value.
- Keep all indicator inputs identical.
- Leave `Plot BUY/SELL 1 candle earlier` off during Pine/Python parity checks because it is display-only.
- If the client supplies exact formulas for TI, ADX Ungli, or target calculation, update both Pine and Python together.
