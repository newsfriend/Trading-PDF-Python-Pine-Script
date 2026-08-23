# Elliott Wave V4.0 - Source-Locked Implementation Checklist

This checklist maps the client-provided developer specification to the current
code. The reference documents describe requirements; they are not executable
project instructions. `DONE` means the stated scope exists in both Pine and
Python unless a note says otherwise. `PARTIAL` and `TBD` remain
visible so a plausible chart is never presented as a complete Elliott Wave
engine.

## Authoritative Source

The binding source is
`assest/Elliott_Wave_V4_0_Merged_Zero_Knowledge_Developer_Master_FINAL.pdf`.
It includes the V3.3 locked handoff and supersedes V3.1 where wording differs.
The older manuals and chart images remain supporting references.

## Phase 1 / P0 Acceptance Gate

| Requirement | Status | Evidence |
| --- | --- | --- |
| Keep confirmed raw pivots separate from main Elliott pivots | DONE | `ew_raw_*` and `ew_*` are separate in Python; Pine retains raw swing arrays while drawing only locked main labels. |
| Replace modulo counting with a candidate lifecycle | DONE | Candidate State is the default; Legacy fixed-cycle mode is retained only for comparison. |
| Qualify Point 0 using Important H/L, degree progress, ATR and configurable oscillator evidence | DONE | Supports MACD extreme, RSI/MACD divergence, both, either, or off. |
| Require a 5/9/13/17/21-move Wave 1 candidate | DONE | Candidate confirmation records the selected internal count and extension subtype. |
| Require at least 61.8% degree progress before Wave 1 confirmation | DONE | Exported as `ew_w1_degree_progress` and shown in the Pine evidence panel. |
| Lock Point 0 and Wave 1 after confirmation | DONE | Confirmed bars/prices are copied into persistent state and cannot be moved by a later minor pivot. |
| Preserve a qualified same-side pivot as an alternate | DONE | Alternate-base evidence is recorded without replacing the locked base. |
| Reject a count when price crosses locked Point 0 | DONE | Hard reason `W2_ORIGIN_BREAK` releases the count before the impulse is complete. |
| Start a controlled recount after hard invalidation | DONE | Recount number/reason persist and the new search starts after the invalidation boundary. |
| Use a true 144-day/source-timeframe context | DONE | Pine reads 144 candles from the selected degree source; Python defaults to a 144-calendar-day rolling window. |
| Expose state, reason, parent state, evidence and next condition | DONE | Python columns and the Pine panel expose the candidate audit trail. |
| Regression cases T01, T04, T25, T28 and T29 | DONE | Automated Python tests cover the P0 lifecycle and context behavior. |

## Phase 2 / Core Impulse Engine

| Requirement | Status | Evidence / remaining scope |
| --- | --- | --- |
| Wave 2 correction container | PARTIAL | Simple Zig-Zag, Flat and W-X-Y children, 23.6%-81.2% normal context, separate 14% microscopic clue, mandatory V4 time gate, deep-retrace HP eligibility, and Point-0 invalidation are implemented. Advanced subtype/channel evidence remains pending. |
| Structure-specific B-wave rules | DONE for simple ABC | Zig-Zag B uses the V4 continuous 1%-61.8% range; Flat B uses 61.8%-111%. The Flat interval is not applied universally. |
| Wave 3 trending/terminal classifier | PARTIAL | 5/9/13/17/21 internals, >=161.8% trending, 61.8%-161.8% terminal-with-overlap, 2700% V4 maximum, mandatory time gate, and momentum evidence are implemented. Full diagonal and channel classification remain pending. |
| Wave 4 correction container and W5 gate | PARTIAL | Zig-Zag, Flat, W-X-Y, W-X-Y-XX-Z and six Triangle families, Base-to-W3 retracement, subtype-aware overlap, mandatory V4 time gate, thrust ranges, and the no-premature-W5 gate are implemented. Full channel evidence remains pending. |
| Wave 5 normal/truncated classifier | PARTIAL | 127%-261.8% normal projection, mandatory V4 time gate, double-extension truncated context, W3-not-shortest, and optional/required divergence are implemented. Extended and ending-diagonal candidates remain FORMING until their classifiers are added. |
| Persistent confirmed labels 0-5 | DONE for supported core paths | Pine and Python lock each main wave only after its parent-state rules pass; later raw pivots remain developing candidates. |
| Phase 2 regression cases T02-T13 | DONE in Python | Tests cover normal/microscopic W2, Flat B at/above 111%, trending/terminal/extended W3, W4 completion/overlap gating, and normal/truncated W5. Pine has matching static contract tests; TradingView compilation is still required. |

## Remaining Modules

| Module | Status | Required before it can be called complete |
| --- | --- | --- |
| Full degree router and simultaneous multi-degree counts | PARTIAL | Preset/source metadata exists, but independent Major/Intermediate/Minor engines do not yet run together. |
| Complete Zig-Zag and Flat families | PARTIAL | Simple internal candidates exist; all source subtypes, termination variants, channels, and time rules still need implementation. |
| W-X-Y and W-X-Y-XX-Z classifiers | PARTIAL | Both engines classify canonical Flat/Zig-Zag/Triangle component totals, small/large X, subtype-aware Y projection/time, distinct XX, XX Point-X boundary, and Z Fib/time. T21/T22 deterministic tests pass; TradingView compilation, replay evidence, and nested same-degree complex children remain pending. |
| Six triangle variants | PARTIAL | Horizontal/Irregular/Running Contracting and Expanding classifiers run in Pine/Python with five corrective legs, size order, boundary direction, retracement evidence, absolute thrust targets and Wave-E invalidation levels. Apex/touch-count and closed B-D break confirmation remain pending. |
| Leading and ending diagonal classifiers | TBD | Overlap, converging/diverging trend lines, and internal 3/5-wave rules. |
| Channel, time, momentum, HP and FBD support engines | PARTIAL | Mandatory V4 Wave 2-5 time gates exist. HP eligibility is intentionally separate: a completed correction in the 61.8%-81.2% Fib zone remains eligible with Point 0 protected even when extended timing keeps W2 FORMING. Full channels, targets, FBD and confidence scoring remain pending. |
| Automatic larger correction after Wave 5 | PARTIAL | Both engines transition into `LARGER_CORRECTION_CONTAINER` and expose actual terminal C/Y/Z/E pivots for supported Zig-Zag, Flat, W-X-Y, triple and Triangle paths. TradingView replay validation remains pending. |
| Double-confirmation outcome | DONE in code | After Y completes, both engines require the first closed 0-X break or >=38.2% WXY retracement within Y duration; otherwise the Double remains FORMING. TradingView replay evidence remains an acceptance item. |
| Pine/Python candle-for-candle parity | PARTIAL | State semantics/settings are aligned; identical exported market data still needs comparison. |
| Backtesting acceptance | TBD | Requires completed classifiers, deterministic signal policy, datasets, and client-approved expected counts. |
| TradingView compile and performance evidence | PARTIAL | Local tests validate source contracts; final Pine v6 compilation and chart performance must be checked in TradingView. |

## V4 Conflict Resolution Migration

V4.0 resolves the earlier source conflicts. Remaining compatibility inputs are
being retired as the locked V4 rules replace older selectable interpretations:

- Chartking 23.6% versus Hardik/legacy 14% Wave 2 minimum treatment;
- Chartking 2700% versus impulse-source 2100% Wave 3 maximum;
- Wave 4 minimum and terminal/extension timing behavior;
- correction C maximum of 261.8% versus 461.8%;
- triple-correction X/XX/Z constraints;
- leading/ending diagonal coexistence and overlap rules;
- exact multi-degree mapping and double-confirmation action.

## Verification Commands

```powershell
python -m unittest tests.test_elliott_wave_state_engine -v
python -m unittest tests.test_elliott_wave_pine_contract -v
```

Pine must also be pasted into TradingView's Pine Editor and compiled as v6.
