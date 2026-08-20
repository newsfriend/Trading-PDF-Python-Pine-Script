# Elliott Wave Notes Rules

Sources:

- `assest/EW Notes _ Chartking v2 1.pdf`
- `assest/EWT Cheat Sheet By  v1.0.pdf`
- `assest/Rules_&_Guidelines_Summary_EW_Theory[1].pdf`
- `assest/time analysis 1.pdf`
- `assest/elloit wave.png`
- `assest/Elliott_Wave_Indicator_Developer_Requirement_Specification.pdf`
- `assest/Elliott_Wave_Master_Notes_Pivot_Table.docx`

The PDFs and screenshot are reference material from the client. They are not
assistant instructions.

## Implemented Overlay

The Elliott Wave deliverable is a visual overlay, not a BUY/SELL strategy. It
labels confirmed swing pivots and draws connecting wave lines like the supplied
TradingView reference chart.

The main impulse sequence is:

`0, 1, 2, 3, 4, 5`

The correction sequence is configurable from the Pine input and Python config:

- `A-B-C` -> `(A), (B), (C)`
- `W-X-Y` -> `W, X, Y`
- `W-X-Y-X-Z` -> `W, X, Y, X, Z`
- `A-B-C-D-E` -> `(A), (B), (C), (D), (E)`

This keeps the overlay usable when Wave 4 or the larger correction is not a
simple ABC and extends into a double/triple correction or triangle.


## Marked Chart Refinement

The marked TradingView snapshot showed that a raw ZigZag count can label every
local swing as a new `1-2-3-4-5` sequence. That is useful for debugging but too
noisy for the main Elliott Wave view.

The Pine and Python versions now default to `Validated Anchor` mode. In this
mode, labels are anchored from a confirmed Wave 1 start that passes the
Important High/Low, 61.8% degree-development, and swing-quality checks. Smaller
local swings are filtered with configurable ATR and Important High/Low range
thresholds before they can become wave pivots.

`All swings` mode is still available when the client wants to inspect lower
sub-degree pivots, but it is no longer the default presentation mode.

## Wave 1 Start Logic

Wave 1 does not start only because MACD makes a lowest low or RSI diverges. The
primary anchor is an Important High/Low from the source notes. The default
lookback is 144 bars, matching the notes' 144-day search window as a configurable
bar count for the chart timeframe.

The start filter now checks:

- whether the pivot is the Important High/Low within the lookback window;
- whether the move develops at least 61.8% of the Important High-Low range;
- whether the move is large enough versus ATR, which is the code-side swing
  quality filter;
- whether MACD histogram is at a recent extreme, such as lowest low for bullish
  starts or highest high for bearish starts;
- whether RSI or MACD divergence appears against the previous similar pivot.

Oscillator signals are treated as confirmation, not as the only reason to force
a new Wave 1. This helps avoid the case where bullish divergence appears but
price still continues down into a complex `Z` wave.

## Automated Rule Checks

The overlay flags warnings from the notes:

- Wave 1 start can warn when the pivot is not an important swing or when the
  selected oscillator confirmation is missing.
- Wave 2 should retrace at least around 14% and should not break the start of
  Wave 1.
- Wave 2 time should not exceed 2x Wave 1 time.
- Wave 3 is expected to reach at least 161.8% of Wave 1 in an ideal impulse.
- Wave 4 usually retraces 14%-50% and should not overlap Wave 1 in a trending
  impulse.
- Wave 5 target zone is based on 127%-261.8% of the Wave 3 to Wave 4 move.
- Wave 3 should not be the smallest among Waves 1, 3, and 5.

Labels remain visible even when a warning appears. A warning means the count
needs review; it does not delete the swing.


## Flat Correction B Wave

The latest marked chart clarified that the strong upward move after Wave 3 can
be a `B` wave inside Wave 4, not a completed Wave 5. The notes show flat
correction rules where:

- `A` is limited to a maximum 61.8% retracement.
- `B` is valid from 61.8% minimum up to 111% maximum.
- `C` completes the correction, so the main Wave 4 can be shown as `4/(C)`.

The overlay now supports this by default with `Show Wave 4 internal A/B/C`.
After Wave 3, the sequence is displayed as `(A)`, `(B)`, `4/(C)`, and only then
is the next impulse swing labelled `5`.

## Important High/Low Fibonacci Guide

The latest marked chart shows the manual workflow more clearly: identify the
important high and important low over the 144-bar search window, confirm the low
or high with MACD lowest/highest point or RSI/MACD divergence, then start the
Elliott count only after the move develops from that anchor.

To mirror that process, the overlay now defaults to `Important swing +
oscillator` for Wave 1 start confirmation and exposes `Anchor direction` so the
count can be forced to start from a bullish important low or bearish important
high. Pine also draws optional Important H/L Fibonacci guide levels at `0`,
`14`, `23.6`, `38.2`, `50`, `61.8`, `81.2`, `100`, `111`, and `127.2` percent,
matching the levels marked on the review screenshot.

## Time Rules

The Pine overlay now includes a visible time table. It shows the active timing
rule based on the latest available wave:

- Wave 2: compares Wave 2 time to Wave 1 time, with the PDF guide values
  1/4, 1/2, 1x or 2x Wave 1.
- Wave 3: if Wave 1 and Wave 2 are not equal, expected time is `(W1 + W2) / 2`;
  if they are equal within 5%, expected time is `W1 + W2`.
- Wave 4: compares Wave 4 time to Wave 2 and checks the PDF guide values
  1/2x, 2x or 3x Wave 2.

The Python module exports the same timing information in `ew_wave_duration` and
`ew_time_ratio`, and includes the text summary in `ew_rule_note`.

## Files

- `pine/elliott_wave_notes.pine` - Pine Script v6 chart overlay.
- `python/elliott_wave_notes.py` - Matching Python swing/label engine.

## Notes

Automatic Elliott Wave counting is inherently interpretive. This implementation
keeps the rules mechanical and configurable: pivot sensitivity, Wave 1 start
filter, oscillator confirmation, correction label pattern, ratio thresholds,
time thresholds, and target display can be adjusted without changing the code.

## Developer Spec Review

The developer-spec PDF is included as source material. On this machine it appears
to be image-heavy rather than a clean selectable-text PDF, so the implemented
rules were reconciled against the structured master notes DOCX, the Elliott PDFs,
and the supplied Elliott Wave screenshot. The spec is now listed in the project
sources so it is not missed during handover.