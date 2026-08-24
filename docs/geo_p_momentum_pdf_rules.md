# GEO P Momentum PDF Rules

Source: `assest/All Setups/4. GEO P MOMENTUM.pdf`

PDF title visible in the supplied material:

`Check List for Momentum Trader : Bollinger Band Challenge with Trendline Break`

## Step 1 - Entry Criteria

### BB Buy

Mandatory conditions:

- Tide - BBUC OR price in upper half.
- Tide - TI uptick, better above zero line.
- Tide and Wave - RSI > 50, better when RSI on Wave crosses above 60.
- Wave - BBUC with TLBO.

Buy rows, scored by the code:

- Wave - above-average volume for BO candle.
- Wave - at least two higher lows on line chart prior to BB challenge, preferred.
- Wave - 5 EMA positive crossover with 13 EMA or 26 EMA in last 3 periods.
- Wave - DI PCO.
- Wave - directional ADX Ungli OR ADX above 15.

Better rows:

- Wave - price above 50 EMA.
- No immediate major resistance.
- Tide - TI above zero.
- Tide and Wave - RSI on Wave crosses above 60.

### BB Sell

Mandatory conditions:

- Tide - BBDC OR price in lower half.
- Tide - TI downtick, better below zero line.
- Tide and Wave - RSI < 50, better when RSI on Wave crosses below 40.
- Wave - BBDC with TLBD.

Sell rows, scored by the code:

- Wave - above-average volume for BD candle.
- Wave - at least two lower highs on line chart prior to BB challenge, preferred.
- Wave - 5 EMA negative crossover with 13 EMA or 26 EMA in last 3 periods.
- Wave - DI NCO.
- Wave - directional ADX Ungli OR ADX above 15.

Better rows:

- Wave - price below 50 EMA.
- No immediate major support.
- Tide - TI below zero.
- Tide and Wave - RSI on Wave crosses below 40.

## Step 2 - Supporting Indicators

- Ignored per latest instruction.
- SO - SOBBO / SOBBD is not used in code.
- Option-chain/OI terms TMG / TMJ are not used in code.

Note: this ignored Step 2 is different from the latest screenshot note that
mentions "line number 2". The implemented line-number-2 refinement is the
Tide/Wave RSI rule from Step 1, not the ignored SOBBO/TMG supporting indicators.

## Timeframe Hierarchy Refinement

Latest screenshot requirement:

- When the execution chart is 15 minutes, Tide must be 4H / `240`.
- When the execution chart is 15 minutes, Wave must be 1H / `60`.
- BUY refinement: Tide 4H must have BBUC and TI uptick, and both Tide 4H RSI
  and Wave 1H RSI must be above 50.
- SELL refinement: bearish mirror using Tide BBDC, TI downtick, and both RSI
  values below 50.

`RSI > 50` is implemented as strictly greater than 50, so values such as 51 or
52 qualify. `RSI < 50` is implemented as strictly less than 50.

The complete `PDF Auto` chart-to-context routing, shared by Pine and Python,
is:

| Execution chart | Tide | Wave |
| --- | --- | --- |
| <=3 minutes | 15 minutes | 5 minutes |
| >3 to 5 minutes | 60 minutes | 15 minutes |
| >5 to 15 minutes | 240 minutes | 60 minutes |
| >15 to 60 minutes | Daily | 240 minutes |
| >60 to 240 minutes | Weekly | Daily |
| Daily | Monthly | Weekly |
| Weekly | Monthly | Monthly |
| Monthly | Same monthly chart | Same monthly chart |

Pine requests a higher Tide/Wave timeframe from its last confirmed source
candle. This prevents a closed execution-chart signal from depending on an
unfinished higher-timeframe candle and later disappearing from history. Python
resampling likewise exposes a higher-timeframe candle only at its closing
timestamp. Manual Tide/Wave selections must be equal to or higher than the
execution chart; lower-timeframe requests are rejected because they cannot
produce reliable Pine/Python parity through `request.security()`.

## Step 3 - Stop Loss

- BUY trade: below BBC candle or below TLBO point.
- SELL trade: above BBC candle or above TLBD point.

## Step 4 - Target

- Calculate based on major support/resistance or Fibonacci extension levels.

## Implementation Notes

The PDF checklist names several proprietary abbreviations without formulas.
The code follows the approved checklist structure and exposes the formula
choices as inputs/constants so they can be replaced if the client supplies a
glossary.
User-supplied implementation instruction overrides the PDF where it says to
ignore Step 2, SOBBO/SOBBD, and TMG/TMJ.

TradingView screenshot review: the circled ADX/DMI areas are interpreted as an
ADX upward hook with +DI/-DI separation in the signal direction.
The screenshot behavior is used only to make the ADX Ungli row mechanical; the
entry gate remains the approved PDF checklist with ignored terms excluded.
