# Fake Breakout / Fake Breakdown Rules

Source: `assest/All Setups/2. FAKE BO BD SETUP.pdf`.

## Mandatory structure

- FBD buy: price trades below the previous low, closes back above it, and the
  following closed candle trades and closes above the breakdown candle high.
- FBO sell: price trades above the previous high, closes back below it, and the
  following closed candle trades and closes below the breakout candle low.
- The default previous level is the prior 20-bar extreme, excluding the current
  candle. This operationalizes the manual's undefined "previous High/Low".
- Stops use the failed-break level. Targets select the farther of one-risk-unit
  measured move or prior major support/resistance.

## Probability evidence

The manual says more satisfied conditions improve probability. Accordingly,
Bollinger touch, reversal candle, Heikin-Ashi color change, MACD direction,
RSI (>40 buy, <60 sell), Stochastic cross, DMI alignment/convergence and high
break candle volume are independently scored. The default requires the band
touch and at least three of eight rows. Divergence and derivatives OI are not
fabricated when their required data is absent from OHLCV.

Signals are evaluated on closed candles by default and do not back-paint onto
the sweep candle.

## Trade lifecycle and validation

Only one setup is treated as active at a time. Its stop and target begin on the
candle after the close-confirmed entry and disappear once either level is hit;
the chart therefore does not present an expired level as a current trade. The
Python backtest uses the same lifecycle. If one OHLC candle touches both stop
and target, it records the stop first as the conservative result because the
intrabar path is unknown.
