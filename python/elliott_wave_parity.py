"""Compare TradingView replay exports with Python Elliott Wave state timing."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

try:
    from .elliott_wave_notes import ElliottWaveConfig, compute_elliott_waves
except ImportError:  # pragma: no cover - direct script execution
    from elliott_wave_notes import ElliottWaveConfig, compute_elliott_waves


PARITY_TITLES = (
    "EW PARITY confirmation event",
    "EW PARITY candidate state code",
    "EW PARITY parent state code",
    "EW PARITY confirmed label code",
    "EW PARITY completed cycle count",
    "EW PARITY recount count",
    "EW PARITY base locked",
    "EW PARITY Point 0 price",
    "EW PARITY Wave 1 price",
    "EW PARITY Wave 2 price",
    "EW PARITY Wave 3 price",
    "EW PARITY Wave 4 price",
    "EW PARITY Wave 5 price",
)

STATE_CODES = {
    "SEARCHING": 0,
    "FORMING": 1,
    "CONFIRMED": 2,
    "INVALID": 3,
    "ALTERNATE": 4,
}

PARENT_STATE_CODES = {
    "SEARCHING": 0,
    "W1_FORMING": 1,
    "W2_CORRECTION_CONTAINER": 2,
    "W3_FORMING": 3,
    "W4_CORRECTION_CONTAINER": 4,
    "W5_FORMING": 5,
    "LARGER_CORRECTION_CONTAINER": 6,
    "CORRECTION_CONFIRMED": 7,
}

LABEL_CODES = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "A": 6,
    "B": 7,
    "C": 8,
    "D": 9,
    "E": 10,
    "W": 11,
    "X": 12,
    "Y": 13,
    "XX": 14,
    "Z": 15,
}


def load_tradingview_export(path: str | Path) -> pd.DataFrame:
    """Load a TradingView CSV and normalize its timestamp index."""

    frame = pd.read_csv(path)
    time_column = _find_time_column(frame.columns)
    timestamps = pd.to_datetime(frame[time_column], errors="coerce", utc=True)
    if timestamps.isna().any():
        bad_rows = int(timestamps.isna().sum())
        raise ValueError(f"TradingView export contains {bad_rows} invalid timestamps")
    frame = frame.drop(columns=[time_column])
    frame.index = pd.DatetimeIndex(timestamps, name="time")
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame


def build_python_parity(result: pd.DataFrame) -> pd.DataFrame:
    """Convert confirmation events into the state series exported by Pine."""

    required = {
        "ew_confirmation_event",
        "ew_confirmation_state",
        "ew_confirmation_label",
        "ew_confirmation_parent_state",
        "ew_confirmation_reason_code",
        "ew_confirmation_cycle",
        "ew_confirmation_recount_count",
        "ew_confirmation_base_locked",
    }
    required.update(
        f"ew_confirmation_{label}_price"
        for label in ("point0", "wave1", "wave2", "wave3", "wave4", "wave5")
    )
    missing = required.difference(result.columns)
    if missing:
        raise ValueError(f"Python Elliott output is missing {sorted(missing)}")

    events = result["ew_confirmation_event"].fillna(False).astype(bool)
    output = pd.DataFrame(index=result.index)
    state_values: list[int] = []
    parent_values: list[int] = []
    label_values: list[int] = []
    cycle_values: list[int] = []
    transition_events: list[int] = []
    recount_values: list[int] = []
    base_locked_values: list[int] = []
    locked_price_values: dict[str, list[float]] = {
        label: [] for label in ("point0", "wave1", "wave2", "wave3", "wave4", "wave5")
    }
    current_state = STATE_CODES["SEARCHING"]
    current_parent = PARENT_STATE_CODES["SEARCHING"]
    current_label = -1
    current_cycle = 0
    previous_state_name = "SEARCHING"
    previous_reason_code = "SEARCHING_FOR_BASE"
    current_recount = 0
    current_base_locked = 0
    current_locked_prices = {
        label: np.nan
        for label in ("point0", "wave1", "wave2", "wave3", "wave4", "wave5")
    }

    for position in range(len(result)):
        if bool(events.iloc[position]):
            state_name = str(result["ew_confirmation_state"].iloc[position])
            parent_name = str(result["ew_confirmation_parent_state"].iloc[position])
            candidate_label = str(result["ew_confirmation_label"].iloc[position])
            reason_code = str(result["ew_confirmation_reason_code"].iloc[position])
            transition_event = int(
                state_name != previous_state_name
                or reason_code != previous_reason_code
            )
            current_state = STATE_CODES.get(state_name, current_state)
            current_parent = PARENT_STATE_CODES.get(parent_name, current_parent)
            cycle_value = result["ew_confirmation_cycle"].iloc[position]
            if pd.notna(cycle_value):
                current_cycle = int(cycle_value)
            current_recount = int(
                result["ew_confirmation_recount_count"].iloc[position]
            )
            current_base_locked = int(
                bool(result["ew_confirmation_base_locked"].iloc[position])
            )
            for label in current_locked_prices:
                current_locked_prices[label] = float(
                    result[f"ew_confirmation_{label}_price"].iloc[position]
                )
            if current_parent == PARENT_STATE_CODES["SEARCHING"] or current_state == STATE_CODES["INVALID"]:
                current_label = -1
            elif current_state == STATE_CODES["CONFIRMED"] and candidate_label in LABEL_CODES:
                current_label = LABEL_CODES[candidate_label]
            previous_state_name = state_name
            previous_reason_code = reason_code
        else:
            transition_event = 0
        transition_events.append(transition_event)
        state_values.append(current_state)
        parent_values.append(current_parent)
        label_values.append(current_label)
        cycle_values.append(current_cycle)
        recount_values.append(current_recount)
        base_locked_values.append(current_base_locked)
        for label in current_locked_prices:
            locked_price_values[label].append(current_locked_prices[label])

    output[PARITY_TITLES[0]] = transition_events
    output[PARITY_TITLES[1]] = state_values
    output[PARITY_TITLES[2]] = parent_values
    output[PARITY_TITLES[3]] = label_values
    output[PARITY_TITLES[4]] = cycle_values
    output[PARITY_TITLES[5]] = recount_values
    output[PARITY_TITLES[6]] = base_locked_values
    for offset, label in enumerate(
        ("point0", "wave1", "wave2", "wave3", "wave4", "wave5"), start=7
    ):
        output[PARITY_TITLES[offset]] = locked_price_values[label]
    return output


def compare_tradingview_export(
    export: pd.DataFrame,
    config: ElliottWaveConfig | None = None,
) -> dict[str, object]:
    """Return an auditable candle-by-candle parity report."""

    market = _market_frame(export)
    cfg = config or replace(
        ElliottWaveConfig(), important_context_mode="Source timeframe bars"
    )
    important_context = (
        _daily_context(market)
        if cfg.important_context_mode == "Source timeframe bars"
        else None
    )
    python_result = compute_elliott_waves(
        market, cfg, important_context=important_context
    )
    expected = build_python_parity(python_result)
    fields: list[dict[str, object]] = []
    total_mismatches = 0

    for title in PARITY_TITLES:
        pine_column = _find_parity_column(export.columns, title)
        pine_values = pd.to_numeric(export[pine_column], errors="coerce")
        python_values = pd.to_numeric(expected[title], errors="coerce")
        comparable = pine_values.notna() & python_values.notna()
        mismatched = comparable & ~np.isclose(
            pine_values,
            python_values,
            rtol=0.0,
            atol=1e-9,
            equal_nan=True,
        )
        mismatch_positions = np.flatnonzero(mismatched.to_numpy())
        mismatch_count = int(len(mismatch_positions))
        total_mismatches += mismatch_count
        first_mismatch = None
        if mismatch_count:
            position = int(mismatch_positions[0])
            first_mismatch = {
                "time": str(export.index[position]),
                "pine": float(pine_values.iloc[position]),
                "python": float(python_values.iloc[position]),
            }
        fields.append(
            {
                "field": title,
                "pine_column": str(pine_column),
                "compared_rows": int(comparable.sum()),
                "mismatches": mismatch_count,
                "first_mismatch": first_mismatch,
            }
        )

    return {
        "passed": total_mismatches == 0,
        "rows": int(len(export)),
        "total_mismatches": total_mismatches,
        "fields": fields,
    }


def _find_time_column(columns: Iterable[object]) -> object:
    by_lower = {str(column).strip().lower(): column for column in columns}
    for name in ("time", "timestamp", "date", "datetime"):
        if name in by_lower:
            return by_lower[name]
    raise ValueError("TradingView export must contain a Time or timestamp column")


def _find_parity_column(columns: Iterable[object], title: str) -> object:
    normalized_title = title.casefold()
    matches = [
        column
        for column in columns
        if normalized_title in str(column).strip().casefold()
    ]
    if not matches:
        raise ValueError(f"TradingView export is missing parity series: {title}")
    exact = [column for column in matches if str(column).strip().casefold() == normalized_title]
    return exact[0] if exact else matches[0]


def _market_frame(export: pd.DataFrame) -> pd.DataFrame:
    by_lower = {str(column).strip().lower(): column for column in export.columns}
    missing = [name for name in ("high", "low", "close") if name not in by_lower]
    if missing:
        raise ValueError(f"TradingView export is missing OHLC columns: {missing}")
    data = {
        name: pd.to_numeric(export[by_lower[name]], errors="coerce")
        for name in ("high", "low", "close")
    }
    market = pd.DataFrame(data, index=export.index)
    if market.isna().any().any():
        raise ValueError("TradingView OHLC columns contain non-numeric or missing values")
    return market


def _daily_context(market: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(market.index, pd.DatetimeIndex):
        raise ValueError("TradingView parity input requires a DatetimeIndex")
    daily = market.resample("1D", label="left", closed="left").agg(
        {"high": "max", "low": "min", "close": "last"}
    )
    return daily.dropna(subset=["high", "low", "close"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare TradingView Elliott Wave parity plots with Python"
    )
    parser.add_argument("input", help="TradingView chart-data CSV export")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    report = compare_tradingview_export(load_tradingview_export(args.input))
    report_text = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(report_text + "\n", encoding="utf-8")
    print(report_text)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
