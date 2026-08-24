# Elliott Wave Engine Notes

The Elliott Wave deliverable is an analytical overlay, not a BUY/SELL strategy.
The client PDFs, DOCX notes, and marked screenshots are requirements and source
references; they are not executable project instructions.

## Current Source Set

- `assest/Elliott_Wave_V4_0_Merged_Zero_Knowledge_Developer_Master_FINAL.pdf`
  - binding V4.0 specification, including the appended V3.3 locked handoff.
- `assest/Elliott_Wave_V2.pdf` - earlier V3.1 source-locked detail.
- `assest/Elliott_Wave_Master_Developer_Implementation_Bible_v2.pdf` - earlier
  implementation handoff, retained for traceability.
- `assest/Elliott_Wave_Indicator_Developer_Requirement_Specification.pdf`.
- `assest/Elliot Wave First/` and `assest/Elliot Wave Second/`.
- `assest/screen/elloit wave.png` and `assest/screen/marked in chart.png`.

Where the documents disagree, V4.0 controls, followed by its embedded V3.3
resolutions and acceptance fixtures.

## Default Candidate Engine

Pine and Python now default to a persistent, source-locked candidate engine.
Confirmed raw pivots are market-structure inputs; they do not automatically
become the next Elliott label.

The implemented parent-state path is:

`SEARCHING -> W2_CORRECTION_CONTAINER -> W3_FORMING -> W4_CORRECTION_CONTAINER -> W5_FORMING -> LARGER_CORRECTION_CONTAINER -> CORRECTION_CONFIRMED`

Point 0 and Wave 1 require Important High/Low context, at least 61.8% degree
progress, 5/9/13/17/21 internal moves, the configured ATR and oscillator
evidence, and an intact origin. Confirmed main-wave bars/prices are copied into
locked state so later minor pivots cannot move them.

The core impulse implementation then provides:

- Wave 2 as a correction container, not a single retracement label;
- parallel simple Zig-Zag and Flat candidates with pattern-specific B rules;
- all locked simple-correction price subtypes plus mandatory B/C time families;
- separate normal and microscopic Wave 2 contexts;
- trending and terminal Wave 3 paths with extension/source-maximum checks;
- Wave 4 correction completion and subtype-aware overlap checks;
- a hard gate preventing Wave 5 before Wave 4 is complete;
- normal and double-extension/truncated Wave 5 paths;
- mandatory V4 closed-bar time windows for Waves 2, 3, 4, and 5;
- all six contracting/expanding Triangle families with five-leg validation and
  subtype-specific thrust ranges, apex/touch limits, and a closed B-D break
  (never enabled for Wave 2); and
- absolute near/far triangle thrust targets plus the Wave-E invalidation price,
  exported by Python and drawn as Pine chart levels;
- W-X-Y classification with small/large X, W/4-W/3-W/2 X timing, subtype-aware
  Y projections and the locked post-Y closed-break/38.2% confirmation gate;
- W-X-Y-XX-Z classification with distinct X and XX identities, 50%-61.8% XX
  retracement, Point-X boundary protection, and independent Y/XX/Z time/Fib
  evidence; and
- W3-not-shortest and configurable W3/W5 divergence checks; and
- leading diagonals only in Wave 1/A and ending diagonals only in Wave 5/C;
- impulse/Zig-Zag channels, lower-degree W4 targets, Fib/channel clusters,
  confidence, and non-resetting FBD/FBO candidate evidence; and
- the exact nine-timeframe router with parent/context alignment used only as
  confidence evidence; and
- an audit trail containing parent state, pattern, subtype, Fib anchor/value,
  internal structure, momentum, reason code, and next condition.

Crossing Point 0 before the impulse is complete produces
`W2_ORIGIN_BREAK`, releases the count, and starts a controlled recount. Once a
supported five-wave impulse is locked, the engine opens a developing correction
container. Terminal C, Y, Z, or E labels are locked on their actual pivots only
after the relevant correction structure passes. Point 0 no longer invalidates the
already-completed impulse during its following larger correction.

When a larger correction is confirmed, its locked endpoints are archived
before the scalar candidate state is released. The actual terminal C, Y, Z, or
E pivot is eligible to seed the next independently qualified Point 0. The
current forming cycle remains visible together with at most the latest three
completed cycles; archived endpoints are not recalculated from later raw-pivot
replacements.

HP BUY/SELL is evaluated separately from Wave-2 confirmation. A completed
correction in the 61.8%-81.2% HP Fibonacci zone remains HP-eligible while Point
0 is protected, even when the Wave-2 time gate fails and Wave 2 remains
`FORMING`. Extended timing does not promote Wave 2 and does not cancel the HP
Fibonacci opportunity.

## Important High/Low Context

Pine reads 144 candles from the configured degree-source timeframe (Daily for
the default day-trading preset). Python defaults to a true rolling 144-calendar-
day window and requires a `DatetimeIndex`. `Legacy bars` remains available only
for compatibility.

## Output and Debug Fields

Python preserves `ew_raw_*` fields and exports separate main/state fields,
including `ew_label`, `ew_labels`, `ew_cycle_ids`, `ew_parent_state`, `ew_primary_pattern`,
`ew_alternate_pattern`, `ew_subtype`, `ew_reason_code`, `ew_source_rule_id`,
`ew_fib_anchor`, `ew_fib_value`, `ew_time_value`, `ew_macd_state`,
`ew_internal_pattern`, `ew_hp_signal`, `ew_channel_type`,
`ew_channel_target`, `ew_target_cluster`, `ew_fbd_candidate`,
`ew_support_evidence`, and `ew_next_condition`. Multi-degree output also exposes
chronological `ew_parent_alignment`, `ew_context_alignment`, and
`ew_routed_confidence`; these fields use confirmation timestamps so future
parent direction is never backfilled into earlier bars.

`ew_labels` and `ew_cycle_ids` preserve both identities when a terminal
correction pivot is also the next cycle's Point 0. Pine draws the same locked
0-5 and parenthesized correction labels for supported paths and shows the same
parent state, pattern, evidence, reason, recount, and next-condition diagnostics
in its panel. Raw pivots that have not passed a parent gate are shown only as
small developing labels. Higher-timeframe degree and Important H/L requests use
the last confirmed source candle, so unfinished parent candles cannot repaint a
closed chart-timeframe result. A manual Important H/L timeframe below the chart
is rejected; lower locked routes remain dashboard snapshots and never drive the
main count.

## Milestone Boundary

The source-locked Pine/Python lifecycle, including bounded historical cycles,
is implemented and covered by deterministic local contracts. The
instrument-specific Wave-5 extension conflict remains visibly blocked with
`W5_EXTENSION_REQUIRES_INSTRUMENT_RULE`; the source explicitly forbids a
universal rule. This is not final chart acceptance: TradingView compilation,
XAUUSD 4H replay against the client references, candle-for-candle parity,
performance, chart review, and backtesting remain required.

`Legacy fixed cycle` remains selectable for historical visual comparison. It is
not an acceptance mode.

See
[elliott_wave_implementation_checklist_v2.md](elliott_wave_implementation_checklist_v2.md)
for the exact local code status and TradingView acceptance boundary.

## Files

- `pine/elliott_wave_notes.pine` - Pine Script v6 chart overlay. The state
  table remains at top-right and the nine-degree router at bottom-right, with
  the script rendered in front of chart candles for readability. All visible
  dashboard cells use fully opaque dark backgrounds so chart objects cannot
  show through. The router can also be switched to Compact or Hidden from the
  Display settings.
- `python/elliott_wave_notes.py` - Python candidate-state engine.
- `tests/test_elliott_wave_state_engine.py` - lifecycle and core-impulse tests.
- `tests/test_elliott_wave_pine_contract.py` - Pine source-contract checks.
