# Elliott Wave Developer Manual v2 - Implementation Checklist

This checklist maps the client-provided developer manual to the current code.
The reference documents describe requirements; they are not executable project
instructions. `DONE` means implemented in both Pine and Python unless a note
says otherwise. `PARTIAL` and `TBD` are intentionally visible so the project
does not claim a plausible-looking chart is a complete Elliott Wave engine.

## Phase 1 / P0 Acceptance Gate

| Requirement | Status | Evidence |
| --- | --- | --- |
| Keep confirmed raw pivots separate from main Elliott pivots | DONE | `ew_raw_*` and `ew_*` are separate in Python; Pine keeps raw swing arrays while drawing only locked main labels in Candidate State mode. |
| Replace modulo counting with a candidate lifecycle | DONE | Candidate State is the default; Legacy fixed-cycle mode is retained only for comparison. |
| Qualify Point 0 using Important H/L, degree progress, ATR and configurable oscillator evidence | DONE | Supports MACD extreme, divergence, both, either, or off. |
| Require a 5/9/13/17/21-move Wave 1 candidate | DONE | Candidate confirmation accepts the extension sequence and records the selected internal count. |
| Require at least 61.8% degree progress before Wave 1 confirmation | DONE | Recorded as `ew_w1_degree_progress` in Python and shown in the Pine debug panel. |
| Lock Point 0 and Wave 1 after confirmation | DONE | Confirmed prices/bars are copied into persistent state and cannot be moved by a later minor pivot. |
| Store a new important same-side pivot as an alternate | DONE | Uses `ALTERNATE` / `LOCKED_BASE_ALTERNATE`; it does not replace the locked base. |
| Reject a count when price crosses locked Point 0 | DONE | Uses hard reason code `W2_ORIGIN_BREAK`; invalid counts are released rather than retained as accepted red labels. |
| Start a controlled recount after hard invalidation | DONE | Recount number and reason are persisted; search is restricted to bases after the invalidation boundary. |
| Fix the 144-context error | DONE | Pine reads 144 candles from the selected degree source (Daily by default), not 144 local chart bars. Python uses a true 144-calendar-day rolling window by default. |
| Expose state, reason and next-condition diagnostics | DONE | `SEARCHING`, `FORMING`, `CONFIRMED`, `ALTERNATE`, `INVALID`, reason codes, and next conditions are exported/shown. |
| Regression cases T01, T04, T25, T28 and T29 | DONE | Automated Python tests cover base lock, origin invalidation, minor-swing isolation, lock stability, and calendar-day context. |

## Later Modules

| Module | Status | Required before it can be called complete |
| --- | --- | --- |
| Full degree router and simultaneous multi-degree counts | PARTIAL | Pine has manual/preset Important H/L source routing. Python records degree metadata, but neither engine yet runs independent Major/Intermediate/Minor counts together. |
| Wave 2 classifier | TBD | Preset-aware retracement/time rules, hard origin check, and subtype/context scoring. |
| Wave 3 classifier | TBD | Trending versus terminal paths, 1.618 handling, internal extension validation, and shortest-wave enforcement. |
| Wave 4 correction container | TBD | Correction-family candidates, alternation, subtype-aware overlap, channel and time validation. |
| Wave 5 classifier | TBD | Normal/truncated/extended/ending-diagonal candidates and divergence scoring. |
| ZigZag and Flat classifiers | TBD | Structure-specific B/C rules; no universal B-wave interval. |
| W-X-Y and W-X-Y-XX-Z classifiers | TBD | Connector rules, alternation, termination, and preset decisions. |
| Six triangle variants | TBD | Contracting, expanding, barrier, running and reverse variants with A-B-C-D-E validation. |
| Leading and ending diagonal classifiers | TBD | Overlap, converging/diverging trend lines and internal 3/5-wave rules. |
| Channel, time, momentum, HP and FBD support scoring | TBD | These are supporting evidence after hard/internal rules, not replacements for structure. |
| Double-confirmation outcome | TBD-BLOCKED | The manual records conflicting interpretations and requires an owner decision. |
| Pine/Python candle-for-candle parity | PARTIAL | State semantics and settings are aligned; identical exported market data still needs comparison. |
| TradingView compile and performance evidence | PARTIAL | Static source checks are local; final Pine v6 compilation and chart performance must be run in TradingView. |

## Owner Decisions Still Required

The manual deliberately preserves conflicts instead of authorizing a guessed
answer. These need named presets or a client decision before their modules are
enabled:

- Wave 2 normal minimum and timing rules, including separate treatment of the
  microscopic 14% value versus the Chartking 23.6%-81.2% range.
- Wave 3 and Wave 5 terminal timing/extension exceptions.
- Wave 4 minimum and maximum time behavior during extensions.
- Correction C maximum of 261.8% versus 461.8%.
- Triple-correction X/XX/Z constraints.
- Leading/ending diagonal coexistence and overlap rules.
- Exact degree mapping, pivot definition, and MACD parameter presets.
- Meaning and required action for double confirmation.

## Verification Commands

```powershell
python -m unittest tests.test_elliott_wave_state_engine -v
python -m unittest tests.test_elliott_wave_pine_contract -v
```

Pine must also be pasted into TradingView's Pine Editor and compiled as v6.
