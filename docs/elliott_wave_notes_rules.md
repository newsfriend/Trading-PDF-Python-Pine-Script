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
- separate normal and microscopic Wave 2 contexts;
- trending and terminal Wave 3 paths with extension/source-maximum checks;
- Wave 4 correction completion and subtype-aware overlap checks;
- a hard gate preventing Wave 5 before Wave 4 is complete;
- normal and double-extension/truncated Wave 5 paths;
- mandatory V4 closed-bar time windows for Waves 2, 3, 4, and 5;
- all six contracting/expanding Triangle families with five-leg validation and
  subtype-specific thrust ranges (never enabled for Wave 2);
- W3-not-shortest and configurable W3/W5 divergence checks; and
- an audit trail containing parent state, pattern, subtype, Fib anchor/value,
  internal structure, momentum, reason code, and next condition.

Crossing Point 0 before the impulse is complete produces
`W2_ORIGIN_BREAK`, releases the count, and starts a controlled recount. Once a
supported five-wave impulse is locked, the engine opens a developing correction
container. A, B, and C are locked on their actual pivots only after a complete
Zig-Zag or Flat terminal structure passes. Point 0 no longer invalidates the
already-completed impulse during its following larger correction.

## Important High/Low Context

Pine reads 144 candles from the configured degree-source timeframe (Daily for
the default day-trading preset). Python defaults to a true rolling 144-calendar-
day window and requires a `DatetimeIndex`. `Legacy bars` remains available only
for compatibility.

## Output and Debug Fields

Python preserves `ew_raw_*` fields and exports separate main/state fields,
including `ew_label`, `ew_parent_state`, `ew_primary_pattern`,
`ew_alternate_pattern`, `ew_subtype`, `ew_reason_code`, `ew_source_rule_id`,
`ew_fib_anchor`, `ew_fib_value`, `ew_time_value`, `ew_macd_state`,
`ew_internal_pattern`, `ew_hp_signal`, and `ew_next_condition`.

Pine draws locked labels 0-5 and A-B-C for supported paths and shows the same parent
state, pattern, evidence, reason, recount, and next-condition diagnostics in its
panel. Raw pivots that have not passed a parent gate are shown only as small
developing labels.

## Explicit Scope Boundary

The current update covers the core impulse and simple larger A-B-C transition,
not the entire V4.0 deliverable. W-X-Y/triples, triangle variants, full
leading/ending diagonals, simultaneous multi-degree routing, channel engines,
full time/HP/FBD scoring, parity validation, and backtesting remain later work.
Unsupported extended/diagonal Wave 5 candidates remain FORMING or INVALID and
are never promoted by pivot order.

`Legacy fixed cycle` remains selectable for historical visual comparison. It is
not an acceptance mode.

See
[elliott_wave_implementation_checklist_v2.md](elliott_wave_implementation_checklist_v2.md)
for the exact `DONE`, `PARTIAL`, `TBD`, and `TBD-BLOCKED` status.

## Files

- `pine/elliott_wave_notes.pine` - Pine Script v6 overlay.
- `python/elliott_wave_notes.py` - Python candidate-state engine.
- `tests/test_elliott_wave_state_engine.py` - lifecycle and core-impulse tests.
- `tests/test_elliott_wave_pine_contract.py` - Pine source-contract checks.
