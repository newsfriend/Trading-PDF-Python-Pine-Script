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
| Replace modulo counting with a candidate lifecycle | DONE | `Candidate State (V4 Full Cycle)` is the chart-facing default. `SEARCHING` cannot draw sequential Elliott labels; Structural Preview and Legacy fixed-cycle are explicitly non-acceptance modes. |
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
| Wave 5 normal/truncated/extended/ED classifier | DONE IN CODE | Normal, double-extension truncated, instrument-gated extension, and ending-diagonal paths include time, divergence, W3-not-shortest, channel/cluster, and FBD/FBO support. C23 extensions are enabled for stocks, futures, forex, commodities and crypto; indices remain disabled by default with an explicit advanced override. |
| Persistent confirmed labels 0-5 | DONE for supported core paths | Pine and Python lock each main wave only after its parent-state rules pass; later raw pivots remain developing candidates. Strict V4 draws no Elliott labels while `SEARCHING`; the former repeating structural map was removed because it could be mistaken for a confirmed count. |
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
| Channel, time, momentum, GUE, HP and FBD support engines | DONE IN CODE | Mandatory time and momentum evidence, HP eligibility, 2-4/parallel-3 and Zig-Zag channels, lower-degree W4 zones, Fib/channel clusters, and non-resetting FBD/FBO nominations are exposed. Bollinger expansion, GMMA alignment, volume and volatility are confidence-only GUE evidence and cannot override a hard Elliott gate. The visible client-reference overlay plots BB 20/2 with a light-blue fill and EMA 13/26/50/60/100, including colored live values on the right price scale. The client nine-level 0/14/23.6/38.2/50/61.8/81.2/100/111 Fib ladder uses the prior completed structural cycle, spans the chart, and keeps readable percentage/price labels right-aligned inside the visible window while the user pans or zooms. |
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

## 2026-08-27 Client Structural Rebuild

The client rejected the sparse strict-mode chart because it did not visibly
produce coherent `1-2-3-4-5` impulses followed by `A-B-C`. The new default
`Client Swing Structure` engine separates that parent chart count from the
exhaustive lower-degree research lifecycle. It uses confirmed filtered pivots,
hard structural transitions instead of modulo numbering, locked completed
cycles, and a mirrored executable Python regression engine. TradingView
accepted the clean 2,942-line revised Pine source through compilation. A
reference-scale replay test now covers two consecutive XAUUSD-style cycles and
proves that terminal `C` is reused as the following `0`, producing one connected
`0-1-2-3-4-5-A-B-C-1-2-3-4-5-A-B-C` path without interleaved parent labels.
Final visual replacement and screenshot acceptance remain pending because the
Basic chart already uses both available indicator slots.

## 2026-08-28 XAUUSD 4H Live Acceptance

The obsolete Elliott instance was replaced with the clean rebuilt source on
`CAPITALCOM:XAUUSD`, 4-hour. TradingView compiled and calculated the script
without a compiler or runtime error, with `Client Swing Structure` confirmed as
the active default engine.

The first live pass exposed an impossible stale state: bearish Wave 2 had been
moved above Point 0 by a same-side raw-pivot replacement, leaving the active
count on an old off-chart structure. The state machine now treats that revision
as `W2_ORIGIN_BREAK_RECOUNT` and includes a deterministic retained-swing rebuild
for impossible legacy geometry. After redeployment, the active parity prices
moved to the current market structure (`0=4697.04`, `1=4605.21`, `2=4673.68`).

The zoomed July-August acceptance frame visibly contains a connected orange
`0-1-2-3-4-5`, a connected teal `(A)-(B)-(C)`, and the next live orange
`0-1-2`. The FBD/FBO overlay was hidden only for the clean visual inspection and
was restored immediately afterward. This satisfies the chart-facing sequence
and continuity complaint; CSV parity remains unavailable on the TradingView
Basic plan and is not used as evidence for this visual acceptance result.

## 2026-08-28 V4 Re-Audit and Corrective Deployment

The two preceding structural-preview sections are historical findings, not the
current acceptance claim. A fresh audit against the controlling V4 notes found
that the preview did not implement all mandatory internal/time/correction gates
and therefore could not remain the default.

The chart now defaults to `Candidate State (V4 Full Cycle)`. The misleading
SEARCHING fallback that converted pivot indices into repeating
`0-1-2-3-4-5/A-B-C` labels was removed. Waves 1, 3, and 5 now require actual
parent impulse geometry in addition to a permitted internal move count, and
Zig-Zag A/C motive legs receive the same structure validation.

The Point-0 development anchor was also corrected: the 144-day window supplies
context/significance, while the nearest preceding significant opposite swing
supplies the 61.8%/100% price and time measurement. On live XAUUSD 4H this
changed strict V4 from an empty SEARCHING state to a locked Point 0 and confirmed
Wave 1 with Wave 2 forming. The last-bar redraw keeps that authoritative path
visible, and the Fib ladder now uses the actual locked Point-0-to-Wave-1 range
instead of the oversized 144-day range. Pine compilation/runtime passed after
these corrections; full replay, exported parity, and client endpoint approval
remain Milestone-3 acceptance items.
