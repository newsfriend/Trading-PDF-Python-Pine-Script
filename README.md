# Trading PDF to Pine & Python

This project converts rule-based trading setups from PDFs, notes, and marked
charts into:

- TradingView indicators and strategies written in Pine Script v6.
- Python 3.10+ signal engines for analysis and backtesting.

The repository currently contains a working **GEO P Momentum** implementation
and a separate **Elliott Wave Notes** overlay. Reference material for the full
setup collection is stored in the repository for future development.

> **Project status:** Active development. Pine and Python share the same rule
> definitions, but candle-for-candle parity must still be validated using the
> same market data, session, timezone, timeframe, and settings.

## Current Implementations

| Feature | TradingView | Python | Status |
| --- | --- | --- | --- |
| GEO P Momentum signals | Indicator | Signal engine | Implemented |
| GEO P Momentum entries and exits | Strategy | Simple backtester | Implemented |
| Elliott Wave notes | Visual overlay | Swing-label engine | Implemented, under refinement |
| Remaining PDF setups | — | — | Reference material only |

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
Wave contexts for the Line #2 refinement.

The formulas used for PDF abbreviations that were not mathematically defined
are documented in [docs/geo_p_momentum_pdf_rules.md](docs/geo_p_momentum_pdf_rules.md).

## Elliott Wave Notes

The Elliott Wave implementation is a separate analytical overlay; it does not
generate GEO P Momentum BUY or SELL signals. It currently provides:

- Confirmed and ATR-filtered swing detection.
- Important High/Low anchoring with a configurable 144-bar lookback.
- MACD-extreme or RSI/MACD-divergence confirmation for Wave 1 starts.
- Main `0-1-2-3-4-5` labels and selectable correction labels.
- Optional internal Wave 4 `(A)-(B)-(C)` structure.
- Flat B-wave validation from 61.8% to 111%.
- Fibonacci guides from 0% through 127.2%.
- Selected timing, retracement, extension, and Wave 5 target warnings.

This is a deterministic, reference-driven swing overlay—not a complete
automatic Elliott Wave or NeoWave classifier. The newer correction and NeoWave
documents are retained as reference material for future validation work.

See [docs/elliott_wave_notes_rules.md](docs/elliott_wave_notes_rules.md) for the
implemented rules and assumptions.

## Repository Layout

```text
Trading-PDF-Python/
├── pine/
│   ├── geo_p_momentum.pine
│   ├── geo_p_momentum_strategy.pine
│   └── elliott_wave_notes.pine
├── python/
│   ├── __init__.py
│   ├── geo_p_momentum.py
│   └── elliott_wave_notes.py
├── docs/
│   ├── geo_p_momentum_pdf_rules.md
│   ├── elliott_wave_notes_rules.md
│   └── first_task_acceptance_checklist.md
├── assest/
│   ├── All Setups/
│   ├── Elliot Wave First/
│   ├── Elliot Wave Second/
│   └── screen/
├── requirements.txt
└── README.md
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
resampling. Elliott Wave analysis requires the OHLC columns.

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
        count_mode="Validated Anchor",
        correction_pattern="A-B-C",
        show_wave4_internal=True,
    ),
)

print(
    waves.loc[
        waves["ew_pivot"],
        ["ew_label", "ew_rule_state", "ew_rule_note", "ew_time_ratio"],
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
- [First setup acceptance checklist](docs/first_task_acceptance_checklist.md)

Source PDFs, Word documents, and chart screenshots are organized under
`assest/`. These files provide implementation context; they are not executable
project components.
