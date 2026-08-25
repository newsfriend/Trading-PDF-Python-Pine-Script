# Elliott Wave V4.0 - Source-Locked Implementation Checklist

This checklist maps the client-provided developer specification to the current
code. The reference documents describe requirements; they are not executable
project instructions. `DONE IN CODE` means the milestone-2 implementation and
deterministic local contracts exist in Pine and Python. It does not mean the
separate milestone-3 TradingView replay, candle-parity, performance, or client
chart acceptance has passed.

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
| Qualify Point 0 using a significant degree swing, Important H/L context, degree progress and time | DONE | The default structural significance gate uses the stronger ATR/range filter. Oscillator evidence supports candidate ranking but does not reject a structurally valid origin. |
| Lock Point 0 at the closed 61.8% development event | DONE | `W1_DEVELOPED` locks Point 0 when the 61.8%-at-half-time or 100%-at-equal-time rule passes. This event is prefix-invariant and is not invented later at the Wave-1 terminal. |
| Require a later 5/9/13/17/21-move Wave 1 terminal | DONE | `W1_FORMING` retains only `0` and `1?`; the Wave-1 endpoint is locked separately after its permitted terminal pivot confirms. |
| Keep 61.8% development separate from the Wave-1 endpoint | DONE | `lockedW1DevelopmentBar`/`ew_fib_value` record the development touch, while `lockedW1Bar`/`ew_locked_wave1_price` remain empty until completion. |
| Preserve locked Point 0 and Wave 1 after their respective confirmations | DONE | Future minor pivots cannot move either locked event; Point-0 protection begins immediately in `W1_FORMING`. |
| Preserve a qualified same-side pivot as an alternate | DONE | Alternate-base evidence is recorded without replacing the locked base. |
| Reject a count when price crosses locked Point 0 | DONE | Hard reason `W2_ORIGIN_BREAK` releases the count before the impulse is complete. |
| Start a controlled recount after hard invalidation | DONE | Recount number/reason persist and the new search starts after the invalidation boundary. |
| Use a true 144-day/source-timeframe context | DONE | Pine reads 144 candles from the selected degree source; Python defaults to a 144-calendar-day rolling window. |
| Expose state, reason, parent state, evidence and next condition | DONE | Python columns and the Pine panel expose the candidate audit trail. |
| Regression cases T01, T04, T25, T28 and T29 | DONE | Automated Python tests cover the P0 lifecycle and context behavior. |

## Phase 2 / Core Impulse Engine

| Requirement | Status | Evidence / remaining scope |
| --- | --- | --- |
| Wave 2 correction container | DONE IN CODE | Simple/complex children, normal/microscopic contexts, mandatory structure/Fib/time gates, HP eligibility, correction-channel evidence, and Point-0 invalidation are implemented. |
| Structure-specific B-wave rules | DONE for simple ABC | Zig-Zag B uses the V4 continuous 1%-61.8% range; Flat B uses 61.8%-111%. The Flat interval is not applied universally. |
| Wave 3 trending/terminal classifier | DONE IN CODE | 5/9/13/17/21 internals, trending/terminal ranges, 2700% maximum, time, momentum, overlap, and lower-degree W4 target-zone support are implemented. |
| Wave 4 correction container and W5 gate | DONE IN CODE | All supported correction families, Base-to-W3 retracement, overlap, time, thrust/channel evidence, and the no-premature-W5 gate are implemented. |
| Wave 5 normal/truncated/ED classifier | DONE IN CODE | Normal, double-extension truncated, and ending-diagonal paths include time, divergence, W3-not-shortest, channel/cluster, and FBD/FBO support. The source-conflicted instrument-specific W5 extension is explicitly blocked with `W5_EXTENSION_REQUIRES_INSTRUMENT_RULE`; it is never generalized. |
| Persistent confirmed labels 0-5 | DONE for supported core paths | Pine and Python lock each main wave only after its parent-state rules pass; later raw pivots remain developing candidates. |
| Retain completed historical cycles | DONE IN CODE | The current forming count and latest three completed cycles are rendered independently. A locked terminal correction can seed the next Point 0, and archive-prefix regression tests prevent later pivots from moving completed endpoints. |
| Phase 2 regression cases T02-T13 | DONE in Python | Tests cover normal/microscopic W2, Flat B at/above 111%, trending/terminal/extended W3, W4 completion/overlap gating, and normal/truncated W5. Pine has matching static contract tests and compiles in TradingView; reference-range replay still remains. |

## Remaining Modules

| Module | Status | Required before it can be called complete |
| --- | --- | --- |
| Locked nine-timeframe degree router | DONE IN CODE | M/W/D/288m/240m/60m/15m/5m/3m routes use 2/3/5/5/5/7/9/12/15 pivots. Python runs independent full engines from a timeframe mapping; Pine keeps isolated route snapshots in a compact dashboard. Parent agreement changes confidence only; 60m uses 240m primary and 288m context. |
| Complete source-resolved Zig-Zag and Flat families | DONE IN CODE | Continuous pattern-specific B ranges, all locked Flat/Zig-Zag price subtypes, A/B/C internals, mandatory B/C time families, LD-A/ED-C paths, and Zig-Zag channel evidence are implemented. |
| W-X-Y and W-X-Y-XX-Z classifiers | DONE IN CODE | Locked component families, small/large X, Y/XX/Z Fib/time, Point-X protection, distinct connectors, and C19 post-Y confirmation are deterministic in both engines. |
| Six triangle variants | DONE IN CODE | Five corrective legs, family geometry, retracement evidence, apex/touch limits, closed B-D break, actual terminal E, thrust targets, and invalidation are implemented. |
| Leading and ending diagonal classifiers | DONE IN CODE | LD is limited to W1/A with 5-3-5-3-5 and source Fib/overlap/wedge gates. ED is limited to W5/C with 3-3-3-3-3, overlap/wedge and divergence gates. |
| Channel, time, momentum, HP and FBD support engines | DONE IN CODE | Mandatory time and momentum evidence, HP eligibility, 2-4/parallel-3 and Zig-Zag channels, lower-degree W4 zones, Fib/channel clusters, confidence, and non-resetting FBD/FBO nominations are exposed. |
| Automatic larger correction after Wave 5 | DONE IN CODE | The engine exposes actual terminal C/Y/Z/E pivots for Zig-Zag, Flat, Double, Triple and Triangle paths, distinct from later confirmation bars. |
| Double-confirmation outcome | DONE in code | After Y completes, both engines require the first closed 0-X break or >=38.2% WXY retracement within Y duration; otherwise the Double remains FORMING. TradingView replay evidence remains an acceptance item. |
| Pine/Python candle-for-candle parity | READY FOR LIVE EVIDENCE | Python exposes pivot-confirmation events separately from historical label placement. Pine exports hidden state/parent/label/cycle/recount and locked endpoint series, and `python/elliott_wave_parity.py` produces a mismatch report from TradingView CSV data using confirmed Daily source context. The XAUUSD 4H export must still be captured and pass. |
| Backtesting acceptance | MILESTONE 3 | Requires client-approved symbols, periods, expected counts, and acceptance thresholds. |
| TradingView compile, replay and performance evidence | PARTIAL LIVE EVIDENCE | Pine v6 compilation and initial XAUUSD 4H runtime verification passed on 2026-08-25. Strict V4 correctly released a stale out-of-degree count and returned to `SEARCHING_FOR_BASE`. Reference-range replay, visual endpoint approval, CSV parity and performance evidence remain required. |

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

Those commands verify the deterministic local contracts. Pine Editor
compilation and an initial XAUUSD 4H runtime check passed on 2026-08-25.
Full replay against the supplied references, visual endpoint approval,
performance, candle parity, and backtesting are still required for acceptance.

## 2026-08-25 Live TradingView Finding

The prior dense screenshot-like output was reproduced only with `Legacy fixed
cycle` and `All swings`. That mode numbers retained pivots mechanically and is
not evidence that the V4 parent-wave rules passed. In strict Candidate State
mode, the live chart exposed two platform-only failures (an undeclared drawing
endpoint and attempts to draw beyond TradingView's bar-index limit) plus a stale
Point-0 lifecycle. The source now guards undrawable history and releases an
active count when its endpoint is evicted or Point 0 leaves the configured
degree context. The corrected script compiled and ran without an error, then
reported `SEARCHING_FOR_BASE` because no current candidate passed all mandatory
V4 gates. This is a valid diagnostic state, not final visual acceptance.
