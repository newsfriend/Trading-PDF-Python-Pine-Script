# Trading PDF to Pine & Python

This project converts rule-based trading setups from PDFs, notes, and marked
charts into:

- TradingView indicators and strategies written in Pine Script v6.
- Python 3.10+ signal engines for analysis and backtesting.

The repository currently contains a working **GEO P Momentum** implementation
and a separate **Elliott Wave Notes** overlay. Its foreground dashboard keeps
the original top-right and bottom-right chart positions. Reference material
for the full setup collection is stored in the repository for future development.

> **Project status:** Active development. Pine and Python share the same rule
> definitions, but candle-for-candle parity must still be validated using the
> same market data, session, timezone, timeframe, and settings.

## Current Implementations

| Feature | TradingView | Python | Status |
| --- | --- | --- | --- |
| GEO P Momentum signals | Indicator | Signal engine | Implemented |
| GEO P Momentum entries and exits | Strategy | Simple backtester | Implemented |
| Elliott Wave engine | V4 full-cycle foreground overlay | V4 full-cycle state engine | Milestone-2 code complete; milestone-3 chart acceptance pending |
| Remaining PDF setups | - | - | Reference material only |

## GEO P Momentum

The GEO P Momentum setup models a Bollinger Band challenge followed by a
trendline or range breakout. Its confirmation logic includes:

- Tide/Wave multi-timeframe direction.
- Bollinger Band upper and lower challenges.
- RSI, volume, EMA crossover, DMI, and ADX confirmation.
- Higher-low and lower-high pivot structure.
- Optional EMA 50 and support/resistance filters.
- Configurable `Fast`, `Balanced`, and `Strict PDF` signal modes.
- Stops, target levels, TradingView alerts, and a Python backtest helper.

The default `PDF Auto` timeframe mapping follows the supplied Tide/Wave
hierarchy. For example, on a 15-minute execution chart it uses 4H Tide and 1H
Wave contexts for the Line #2 refinement. Python uses the same intraday,
daily, weekly, and monthly routing branches as both Pine scripts.

The formulas used for PDF abbreviations that were not mathematically defined
are documented in [docs/geo_p_momentum_pdf_rules.md](docs/geo_p_momentum_pdf_rules.md).

## Elliott Wave Notes

The Elliott Wave implementation is a separate analytical overlay; it does not
generate GEO P Momentum BUY or SELL signals. Its source-locked candidate engine
keeps the dashboard above chart candles and now provides:

- Confirmed and ATR-filtered swing detection.
- Separate raw pivots and main Elliott labels.
- Degree-source Important High/Low context (Daily by default in Pine) and a
  true 144-calendar-day context in Python.
- Configurable MACD-extreme and RSI/MACD-divergence base confirmation.
- Wave 1 candidates with 5/9/13/17/21 internal moves and 61.8% degree progress.
- Persistent Point 0/Wave 1 locking so later small swings cannot move the count.
- Hard origin invalidation, reason codes, alternate bases, and controlled recounts.
- Wave 2 and Wave 4 correction containers with parallel simple Zig-Zag/Flat
  candidates and pattern-specific B-wave ranges.
- Trending/terminal Wave 3 and normal/truncated Wave 5 paths, including
  extension, overlap, shortest-wave, and divergence checks.
- Mandatory V4 closed-bar confirmation windows for Waves 2-5.
- Locked Zig-Zag/Flat subtypes with mandatory B/C time families and
  source-specific B ranges.
- Leading diagonals in Wave 1/A and ending diagonals in Wave 5/C, with locked
  internal structures, overlap, wedge, Fib, and divergence gates.
- Six Triangle families with A-B-C-D-E structure, boundary/size checks, and
  apex/touch limits, a closed B-D break, thrust targets, and Wave-E invalidation.
- Automatic W-X-Y and W-X-Y-XX-Z correction candidates with distinct X/XX
  connectors, component Fib/time gates, X-boundary validation, and V4 post-Y
  confirmation by closed 0-X break or 38.2% WXY retracement.
- Persistent labels 0-5 followed by validated A-B-C, W-X-Y, W-X-Y-XX-Z, or
  A-B-C-D-E, with parent-state gates
  that prevent premature Wave 5 or correction labels.
- Closed-bar FORMING, CONFIRMED, INVALID, recount, correction-complete, and HP alerts.
- HP Fibonacci opportunities remain visible during extended Wave-2 timing;
  timing can keep W2 FORMING without cancelling a structurally valid HP zone.
- Impulse/Zig-Zag channels, lower-degree W4 zones, Fib/channel clusters,
  confidence, and non-resetting FBD/FBO candidate evidence.
- A locked M/W/D/288m/240m/60m/15m/5m/3m router with exact pivot defaults,
  parent/context alignment, a compact Pine dashboard, and independent Python
  engine results through `compute_elliott_waves_multi_degree`.
- Auditable pattern, subtype, Fib, time, momentum, reason, and next-condition
  output.

This completes the milestone-2 Pine/Python engine code. The source-conflicted,
instrument-specific Wave-5 extension remains explicitly blocked instead of
being generalized. TradingView compilation/replay, candle-for-candle parity,
performance checks, chart validation, and backtesting are the separate
milestone-3 acceptance scope. The old modulo-style sequence is available only
as `Legacy fixed cycle` comparison mode.

See [docs/elliott_wave_notes_rules.md](docs/elliott_wave_notes_rules.md) for the
implemented rules and assumptions.

## Repository Layout

```text
Trading-PDF-Python/
|-- pine/
|   |-- geo_p_momentum.pine
|   |-- geo_p_momentum_strategy.pine
|   `-- elliott_wave_notes.pine
|-- python/
|   |-- __init__.py
|   |-- geo_p_momentum.py
|   `-- elliott_wave_notes.py
|-- docs/
|   |-- geo_p_momentum_pdf_rules.md
|   |-- elliott_wave_notes_rules.md
|   |-- elliott_wave_implementation_checklist_v2.md
|   `-- first_task_acceptance_checklist.md
|-- tests/
|   |-- test_elliott_wave_state_engine.py
|   `-- test_elliott_wave_pine_contract.py
|-- assest/
|   |-- All Setups/
|   |-- Elliot Wave First/
|   |-- Elliot Wave Second/
|   `-- screen/
|-- requirements.txt
`-- README.md
```

The existing `assest` directory name is preserved to avoid breaking project
paths and history.

## TradingView Usage

1. Open TradingView and create a new script in the Pine Editor.
2. Copy one of the following files into the editor:
   - [pine/geo_p_momentum.pine](pine/geo_p_momentum.pine) for BUY/SELL markers
     and alerts.
   - [pine/geo_p_momentum_strategy.pine](pine/geo_p_momentum_strategy.pine) for
     entries, exits, stops, targets, and Strategy Tester results.
   - [pine/elliott_wave_notes.pine](pine/elliott_wave_notes.pine) for the
     Elliott Wave visual overlay.
3. Add the script to the chart and configure its inputs.
4. Use the same inputs in Pine and Python when comparing their output.

The `Plot BUY/SELL 1 candle earlier` option changes only marker placement. It
does not move alerts, strategy orders, or Python signals because doing so would
require future confirmation and could repaint.

## Python Usage

### Installation

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

Input data for GEO P Momentum must contain `open`, `high`, `low`, `close`, and
`volume` columns. A `DatetimeIndex` is recommended for multi-timeframe
resampling and is required by the default Elliott Wave calendar-day context.
Elliott Wave analysis requires the `high`, `low`, and `close` columns.

### GEO P Momentum signals

```python
import pandas as pd

from python.geo_p_momentum import (
    GeoPMomentumConfig,
    backtest_signals,
    compute_signals,
)

candles = (
    pd.read_csv("xauusd_15m.csv", parse_dates=["time"])
    .set_index("time")
)

config = GeoPMomentumConfig(
    chart_timeframe="15",
    signal_mode="Balanced",
)

signals = compute_signals(candles, config)
trades = backtest_signals(signals)

print(signals.loc[signals["buy_signal"] | signals["sell_signal"]])
print(trades)
```

### Elliott Wave overlay data

```python
from python.elliott_wave_notes import ElliottWaveConfig, compute_elliott_waves

waves = compute_elliott_waves(
    candles,
    ElliottWaveConfig(
        engine_mode="Candidate State",
        degree_preset="Chartking Day Trading",
        important_context_mode="Calendar days",
    ),
)

print(
    waves.loc[
        waves["ew_raw_pivot"] | waves["ew_pivot"],
        ["ew_label", "ew_engine_state", "ew_reason_code", "ew_rule_note"],
    ]
)
```

### Command line

```bash
python python/geo_p_momentum.py xauusd_15m.csv \
  --time-column time \
  --chart-timeframe 15 \
  --signal-mode Balanced \
  --output signals.csv
```

On Windows PowerShell, place the command on one line or replace each `\` with a
PowerShell backtick.

## Signal Modes

| Mode | Requirement |
| --- | --- |
| `Fast` | Mandatory PDF conditions only |
| `Balanced` | Mandatory conditions plus 3 of 5 scored rows |
| `Strict PDF` | Mandatory conditions plus all 5 scored rows |

`Balanced` is the default. Optional “Better” confirmations can be enabled
separately. PDF Step 2 (`SOBBO/SOBBD` and `TMG/TMJ`) is intentionally excluded
from active signal logic following the latest project instruction.

## Pine/Python Comparison

For the closest possible result between TradingView and Python:

- Use identical OHLCV candles and indicator inputs.
- Match the exchange session, timezone, and candle-close timestamps.
- Match the chart, Tide, and Wave timeframes.
- Keep the signal mode and required Better confirmations identical.
- Disable the display-only earlier-marker option during comparison.
- Compare confirmed signal bars before comparing backtest performance.

The Pine strategy includes 0.01% commission. The current Python backtest helper
reports point-based results and does not yet model equivalent fees or slippage,
so performance totals should not be treated as directly interchangeable.

## Documentation

- [GEO P Momentum rule mapping](docs/geo_p_momentum_pdf_rules.md)
- [Elliott Wave implementation notes](docs/elliott_wave_notes_rules.md)
- [Elliott Wave v2 implementation checklist](docs/elliott_wave_implementation_checklist_v2.md)
- [First setup acceptance checklist](docs/first_task_acceptance_checklist.md)

Source PDFs, Word documents, and chart screenshots are organized under
`assest/`. These files provide implementation context; they are not executable
project components.
