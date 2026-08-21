# Elliott Wave V3.1 - Source-Locked Implementation Checklist

This checklist maps the client-provided developer specification to the current
code. The reference documents describe requirements; they are not executable
project instructions. `DONE` means the stated scope exists in both Pine and
Python unless a note says otherwise. `PARTIAL`, `TBD`, and `TBD-BLOCKED` remain
visible so a plausible chart is never presented as a complete Elliott Wave
engine.

## Authoritative Source

The current implementation source is `assest/Elliott_Wave_V2.pdf`, titled
*Elliott Wave / NeoWave - 100% Source-Locked Master Developer Specification
V3.1*. It supersedes the earlier implementation handoff where the two documents
differ. The older manuals and chart images remain as supporting references.

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
| Wave 2 correction container | PARTIAL | Simple Zig-Zag and Flat children, 23.6%-81.2% normal context, separate 14% microscopic clue, timing diagnostic, deep-retrace HP eligibility, and Point-0 invalidation are implemented. W-X-Y and advanced correction subtypes remain pending. |
| Structure-specific B-wave rules | DONE for simple ABC | Zig-Zag B uses 1%-50%; Flat B uses 61.8%-111%. The Flat interval is not applied universally. |
| Wave 3 trending/terminal classifier | PARTIAL | 5/9/13/17/21 internals, >=161.8% trending, 61.8%-161.8% terminal-with-overlap, 2100%/2700% source presets, and momentum evidence are implemented. Full diagonal and channel classification remain pending. |
| Wave 4 correction container and W5 gate | PARTIAL | Simple correction completion, Base-to-W3 retracement, normal/terminal maximums, subtype-aware overlap, and the no-premature-W5 gate are implemented. Complex corrections, channeling, and full time scoring remain pending. |
| Wave 5 normal/truncated classifier | PARTIAL | 127%-261.8% normal projection, double-extension truncated context, W3-not-shortest, and optional/required divergence are implemented. Extended and ending-diagonal Wave 5 paths remain blocked as `TBD_BLOCKED`. |
| Persistent confirmed labels 0-5 | DONE for supported core paths | Pine and Python lock each main wave only after its parent-state rules pass; later raw pivots remain developing candidates. |
| Phase 2 regression cases T02-T13 | DONE in Python | Tests cover normal/microscopic W2, Flat B at/above 111%, trending/terminal/extended W3, W4 completion/overlap gating, and normal/truncated W5. Pine has matching static contract tests; TradingView compilation is still required. |

## Remaining Modules

| Module | Status | Required before it can be called complete |
| --- | --- | --- |
| Full degree router and simultaneous multi-degree counts | PARTIAL | Preset/source metadata exists, but independent Major/Intermediate/Minor engines do not yet run together. |
| Complete Zig-Zag and Flat families | PARTIAL | Simple internal candidates exist; all source subtypes, termination variants, channels, and time rules still need implementation. |
| W-X-Y and W-X-Y-XX-Z classifiers | TBD | Connector rules, alternation, termination, and source-preset decisions. |
| Six triangle variants | TBD | Contracting, expanding, barrier, running, and reverse variants with A-B-C-D-E validation. |
| Leading and ending diagonal classifiers | TBD | Overlap, converging/diverging trend lines, and internal 3/5-wave rules. |
| Channel, time, momentum, HP and FBD support engines | PARTIAL | Momentum diagnostics and HP eligibility exist. They do not mutate the count; full project filters and scoring are pending. |
| Automatic larger correction after Wave 5 | TBD | The engine stops at `IMPULSE_CONFIRMED` and opens an `A?` correction container without inventing a pattern. |
| Double-confirmation outcome | TBD-BLOCKED | Conflicting source interpretations require an owner decision. |
| Pine/Python candle-for-candle parity | PARTIAL | State semantics/settings are aligned; identical exported market data still needs comparison. |
| Backtesting acceptance | TBD | Requires completed classifiers, deterministic signal policy, datasets, and client-approved expected counts. |
| TradingView compile and performance evidence | PARTIAL | Local tests validate source contracts; final Pine v6 compilation and chart performance must be checked in TradingView. |

## Source Conflicts Kept Explicit

The V3.1 specification preserves several source conflicts. The implementation
uses named configuration modes or reports a blocked subtype instead of silently
choosing one interpretation:

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
