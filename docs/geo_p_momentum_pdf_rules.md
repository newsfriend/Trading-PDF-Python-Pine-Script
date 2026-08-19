# GEO P Momentum PDF Rules

Source: `assest/GEO P MOMENTUM (1).pdf`

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
