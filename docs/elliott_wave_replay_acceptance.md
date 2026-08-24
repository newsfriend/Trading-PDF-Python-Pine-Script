# Elliott Wave TradingView Replay Acceptance

This procedure is the final chart and parity gate for the selected-timeframe
Elliott Wave engine. Local unit tests do not replace it.

## Required Chart

- Symbol: `CAPITALCOM:XAUUSD` (the feed shown in the client references).
- Timeframe: 4 hours.
- History: export at least 2025-09-01 through 2026-08-25. The visible
  acceptance range begins in April 2026, while the earlier candles warm up the
  144 confirmed Daily source-bar context used by both Pine and parity Python.
- Engine: `Candidate State (V4 Full Cycle)`.
- Degree preset: `Chartking Day Trading`.
- Pivot left/right: `5 / 5`.
- Completed cycles retained: `3`.
- Keep the remaining V4 inputs at their committed defaults unless a compared
  reference explicitly documents a different value.

## Compile and Visual Gate

1. Replace the Pine Editor contents with `pine/elliott_wave_notes.pine` and
   select **Add to chart**.
2. Record the Pine compiler result. Any compiler error fails acceptance.
3. Hide unrelated overlays while taking the acceptance screenshots. They may
   be re-enabled after the Elliott labels have been checked.
4. Capture the same April-August and late-June-August ranges as the two client
   references.
5. Confirm that numbered parent waves, combined Wave-2/Wave-4 correction
   terminals, parenthesized larger corrections, connected paths, and Point 0
   occur on the intended swing pivots.
6. Use Bar Replay from the beginning of the range. Only FORMING endpoints may
   move. Once a label confirms, advancing replay must not move it unless the
   chart records a hard invalidation and controlled recount.
7. Confirm that the current forming cycle and no more than the latest three
   completed cycles remain visible.

## Candle-Parity Export

The Pine script publishes hidden `EW PARITY ...` plots in the Data Window. They
do not clutter the chart but are included in TradingView chart-data exports.

1. Export chart data from the validated XAUUSD 4H chart as CSV.
2. Include the Elliott Wave indicator values in the export.
3. Run:

```powershell
python python/elliott_wave_parity.py path\to\tradingview_xauusd_4h.csv --output output\xauusd_4h_parity.json
```

The report compares confirmation-event timing, candidate state, parent state,
last confirmed label, completed-cycle and recount counts, base-lock state, and
the locked Point-0/Wave-1-through-Wave-5 prices on every exported candle. A
non-zero mismatch count fails parity and must be investigated before client
acceptance.

State codes are `0 SEARCHING`, `1 FORMING`, `2 CONFIRMED`, `3 INVALID`, and
`4 ALTERNATE`. Parent-state codes run from `0 SEARCHING` through
`6 CORRECTION_CONFIRMED`. Label codes are `0-5`, followed by `6 A`, `7 B`,
`8 C`, `9 D`, `10 E`, `11 W`, `12 X`, `13 Y`, `14 XX`, and `15 Z`; `-1`
means no locked label in the active cycle.

## Acceptance Evidence

Keep these artifacts together:

- compiler-success screenshot;
- full-chart screenshot for each client reference range;
- at least three replay checkpoints showing locked labels do not move;
- TradingView CSV export;
- JSON parity report with zero mismatches; and
- a short discrepancy note for any intentional difference from the external
  reference indicator, citing the controlling V4 rule.
