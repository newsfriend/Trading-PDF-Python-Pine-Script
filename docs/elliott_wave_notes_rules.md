# Elliott Wave Engine Notes

The Elliott Wave deliverable is an analytical overlay, not a BUY/SELL strategy.
The client reference PDFs, DOCX files, and marked screenshots describe the
requirements; they are not executable project instructions.

## Current Source Set

- `assest/Elliott_Wave_Master_Developer_Implementation_Bible_v2.pdf`
- `assest/Elliott_Wave_Indicator_Developer_Requirement_Specification.pdf`
- `assest/Elliot Wave First/`
- `assest/Elliot Wave Second/`
- `assest/screen/elloit wave.png`
- `assest/screen/marked in chart.png`

## Current Default: Candidate State Phase 1

Pine and Python now default to a persistent candidate engine. Confirmed raw
ZigZag pivots are only market-structure inputs; they do not automatically
become the next Elliott label.

The lifecycle is:

`SEARCHING -> FORMING -> CONFIRMED -> ALTERNATE or INVALID -> controlled recount`

Point 0 and Wave 1 are confirmed only when the candidate:

- starts at the selected Important High/Low degree context;
- follows the selected bullish/bearish direction;
- develops at least 61.8% of that context range;
- contains 5, 9, 13, 17, or 21 internal raw moves;
- passes the configured ATR quality threshold;
- passes the configured MACD-extreme and/or RSI/MACD-divergence rule; and
- does not cross its origin during formation.

After confirmation, Point 0 and Wave 1 are copied into locked state. A later
minor pivot cannot move them or advance the main count. A new important
same-side pivot is reported as `ALTERNATE`. Crossing Point 0 produces hard
reason `W2_ORIGIN_BREAK`, releases the count, and starts a logged recount after
the invalidation boundary.

## Important High/Low Context

The previous implementation treated 144 as local chart bars. That makes the
context radically different on 15-minute, hourly, daily, and monthly charts.

- Pine reads 144 candles from the configured degree source timeframe. The
  default Chartking Day Trading preset uses Daily context even on an intraday
  chart.
- Python defaults to a rolling 144-calendar-day window and requires a
  `DatetimeIndex`. `Legacy bars` is available only for compatibility.

Pine includes initial Chartking/Hardik source presets and a manual source
timeframe. Full simultaneous multi-degree routing remains a later module.

## Output and Debug Fields

Python preserves raw-pivot fields and exports separate main/state fields,
including:

- `ew_raw_pivot`, `ew_raw_side`, `ew_raw_confirmed_at`;
- `ew_pivot`, `ew_label`, `ew_confirmed_at`;
- `ew_engine_state`, `ew_candidate_label`, `ew_reason_code`;
- `ew_base_locked`, `ew_base_price`, `ew_w1_degree_progress`;
- `ew_internal_count`, `ew_recount_count`, `ew_alternate_bases`; and
- `ew_next_condition`, `ew_degree`, `ew_degree_timeframe`.

Pine shows the corresponding state, degree, locked base, Wave 1 evidence,
reason, recount count, alternate count, and next module in its panel.

## Legacy Mode

`Legacy fixed cycle` remains selectable for comparison with earlier charts. It
uses the old modulo label sequence and configurable display patterns. It is not
the accepted developer-manual engine and must not be used as completion
evidence.

## Scope Boundary

Phase 1 intentionally stops after Point 0/Wave 1 foundation and recount safety.
Wave 2-5, ZigZag, Flat, W-X-Y, triple correction, triangles, diagonals,
channels, time scoring, HP, and FBD require their later classifiers. The engine
reports developing pivots without promoting them to main labels until those
modules exist.

See
[elliott_wave_implementation_checklist_v2.md](elliott_wave_implementation_checklist_v2.md)
for the exact `DONE`, `PARTIAL`, `TBD`, and owner-decision status.

## Files

- `pine/elliott_wave_notes.pine` - Pine Script v6 overlay.
- `python/elliott_wave_notes.py` - Python state engine.
- `tests/test_elliott_wave_state_engine.py` - Phase-1 lifecycle regressions.
- `tests/test_elliott_wave_pine_contract.py` - Pine source contract checks.
