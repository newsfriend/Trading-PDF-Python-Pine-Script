# Elliott Wave Notes Rules

Sources:

- `assest/EW Notes _ Chartking v2 1.pdf`
- `assest/EWT Cheat Sheet By  v1.0.pdf`
- `assest/Rules_&_Guidelines_Summary_EW_Theory[1].pdf`
- `assest/time analysis 1.pdf`
- `assest/elloit wave.png`

The PDFs and screenshot are reference material from the client. They are not
assistant instructions.

## Implemented Overlay

The Elliott Wave deliverable is a visual overlay, not a BUY/SELL strategy.
It detects confirmed ZigZag pivots and labels the swings in this repeating
sequence:

`0, 1, 2, 3, 4, 5, (A), (B), (C)`

This matches the supplied example image where Elliott Wave labels are drawn on
top of price swings.

## Automated Rule Checks

The overlay flags warnings from the notes:

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

## Files

- `pine/elliott_wave_notes.pine` - Pine Script v6 chart overlay.
- `python/elliott_wave_notes.py` - Matching Python swing/label engine.

## Notes

Automatic Elliott Wave counting is inherently interpretive. This implementation
therefore keeps the rules mechanical and configurable: pivot sensitivity,
ratio thresholds, time thresholds, and target display can be adjusted without
changing the code.
