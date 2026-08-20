"""Elliott Wave overlay engine based on the supplied notes.

The module produces deterministic swing labels for the visual Elliott Wave
overlay. It does not try to "predict" a wave count; it labels confirmed ZigZag
pivots and flags rule warnings from the notes so the count can be reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ElliottWaveConfig:
    """Configurable values shared with ``pine/elliott_wave_notes.pine``."""

    pivot_left: int = 5
    pivot_right: int = 5
    max_swings: int = 45
    wave2_min_retrace: float = 0.14
    wave2_max_time: float = 2.0
    wave3_min_extension: float = 1.618
    wave4_min_retrace: float = 0.14
    wave4_max_retrace: float = 0.50
    wave5_min_extension: float = 1.27
    wave5_max_extension: float = 2.618


@dataclass(frozen=True)
class _Swing:
    position: int
    confirmed_position: int
    index: object
    confirmed_index: object
    price: float
    kind: int  # 1 = pivot high, -1 = pivot low


def compute_elliott_waves(
    candles: pd.DataFrame, config: ElliottWaveConfig | None = None
) -> pd.DataFrame:
    """Return OHLC data with Elliott Wave labels on confirmed swing pivots."""

    cfg = config or ElliottWaveConfig()
    source = _normalize_ohlc(candles)
    pivots = _detect_pivots(source, cfg)
    swings = _build_swings(pivots, cfg.max_swings)

    result = source.copy()
    result["ew_pivot"] = False
    result["ew_confirmed_at"] = pd.Series(index=result.index, dtype="object")
    result["ew_label"] = pd.Series(index=result.index, dtype="object")
    result["ew_phase"] = np.nan
    result["ew_cycle"] = np.nan
    result["ew_rule_state"] = pd.Series(index=result.index, dtype="object")
    result["ew_rule_note"] = pd.Series(index=result.index, dtype="object")
    result["ew_wave5_min_target"] = np.nan
    result["ew_wave5_max_target"] = np.nan

    for wave_index, swing in enumerate(swings):
        phase = wave_index % 9
        cycle = wave_index // 9
        state, note = _rule_state(swings, wave_index, cfg)
        result.loc[swing.index, "ew_pivot"] = True
        result.loc[swing.index, "ew_confirmed_at"] = swing.confirmed_index
        result.loc[swing.index, "ew_label"] = _phase_label(phase)
        result.loc[swing.index, "ew_phase"] = phase
        result.loc[swing.index, "ew_cycle"] = cycle
        result.loc[swing.index, "ew_rule_state"] = state
        result.loc[swing.index, "ew_rule_note"] = note

        if phase == 4:
            min_target, max_target = _wave5_targets(swings, wave_index, cfg)
            result.loc[swing.index, "ew_wave5_min_target"] = min_target
            result.loc[swing.index, "ew_wave5_max_target"] = max_target

    return result


def _normalize_ohlc(candles: pd.DataFrame) -> pd.DataFrame:
    normalized = candles.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    missing = [column for column in ("high", "low", "close") if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required OHLC columns: {missing}")
    return normalized.sort_index()


def _detect_pivots(source: pd.DataFrame, cfg: ElliottWaveConfig) -> list[_Swing]:
    highs = source["high"].astype(float).to_numpy()
    lows = source["low"].astype(float).to_numpy()
    pivots: list[_Swing] = []

    for position in range(cfg.pivot_left, len(source) - cfg.pivot_right):
        confirmed_position = position + cfg.pivot_right
        high_window = highs[position - cfg.pivot_left : position + cfg.pivot_right + 1]
        low_window = lows[position - cfg.pivot_left : position + cfg.pivot_right + 1]

        if not np.isnan(high_window).any() and highs[position] == np.max(high_window):
            pivots.append(
                _Swing(
                    position,
                    confirmed_position,
                    source.index[position],
                    source.index[confirmed_position],
                    float(highs[position]),
                    1,
                )
            )
        if not np.isnan(low_window).any() and lows[position] == np.min(low_window):
            pivots.append(
                _Swing(
                    position,
                    confirmed_position,
                    source.index[position],
                    source.index[confirmed_position],
                    float(lows[position]),
                    -1,
                )
            )

    pivots.sort(key=lambda item: (item.position, -item.kind))
    return pivots


def _build_swings(pivots: list[_Swing], max_swings: int) -> list[_Swing]:
    swings: list[_Swing] = []

    for pivot in pivots:
        if not swings:
            swings.append(pivot)
            continue

        last = swings[-1]
        if pivot.position == last.position and pivot.kind != last.kind:
            last_distance = abs(pivot.price - (swings[-2].price if len(swings) > 1 else last.price))
            current_distance = abs(last.price - (swings[-2].price if len(swings) > 1 else pivot.price))
            if last_distance > current_distance:
                swings[-1] = pivot
            continue

        if pivot.kind == last.kind:
            more_extreme = pivot.price > last.price if pivot.kind == 1 else pivot.price < last.price
            if more_extreme:
                swings[-1] = pivot
        else:
            swings.append(pivot)

        if len(swings) > max_swings:
            swings = swings[-max_swings:]

    return swings


def _phase_label(phase: int) -> str:
    return {
        0: "0",
        1: "1",
        2: "2",
        3: "3",
        4: "4",
        5: "5",
        6: "(A)",
        7: "(B)",
        8: "(C)",
    }[phase]


def _rule_state(
    swings: list[_Swing], wave_index: int, cfg: ElliottWaveConfig
) -> tuple[str, str]:
    phase = wave_index % 9
    cycle_start = wave_index - phase
    if cycle_start < 0:
        return "ok", ""

    if phase == 2 and wave_index >= 2:
        p0, p1, p2 = (swings[cycle_start + offset].price for offset in range(3))
        t0, t1, t2 = (swings[cycle_start + offset].position for offset in range(3))
        bullish = p1 > p0
        wave1 = abs(p1 - p0)
        retrace = _safe_ratio(abs(p1 - p2), wave1)
        time_ratio = _safe_ratio(max(1, t2 - t1), max(1, t1 - t0))
        invalid = p2 <= p0 if bullish else p2 >= p0
        warning = retrace < cfg.wave2_min_retrace or time_ratio > cfg.wave2_max_time
        return _state(invalid, warning), (
            f"Wave 2 retrace={retrace:.2%}, time={time_ratio:.2f}x Wave 1"
        )

    if phase == 3 and wave_index >= 3:
        p0, p1, p2, p3 = (swings[cycle_start + offset].price for offset in range(4))
        ratio = _safe_ratio(abs(p3 - p2), abs(p1 - p0))
        return _state(False, ratio < cfg.wave3_min_extension), (
            f"Wave 3={ratio:.2%} of Wave 1"
        )

    if phase == 4 and wave_index >= 4:
        p1, p2, p3, p4 = (swings[cycle_start + offset].price for offset in range(1, 5))
        bullish = p3 > p2
        retrace = _safe_ratio(abs(p3 - p4), abs(p3 - p2))
        invalid = p4 <= p1 if bullish else p4 >= p1
        warning = retrace < cfg.wave4_min_retrace or retrace > cfg.wave4_max_retrace
        return _state(invalid, warning), f"Wave 4 retrace={retrace:.2%}"

    if phase == 5 and wave_index >= 5:
        p0, p1, p2, p3, p4, p5 = (
            swings[cycle_start + offset].price for offset in range(6)
        )
        wave1 = abs(p1 - p0)
        wave3 = abs(p3 - p2)
        wave5 = abs(p5 - p4)
        ratio = _safe_ratio(wave5, abs(p3 - p4))
        invalid = wave3 < wave1 and wave3 < wave5
        warning = ratio < cfg.wave5_min_extension or ratio > cfg.wave5_max_extension
        return _state(invalid, warning), f"Wave 5={ratio:.2%} of Wave 3-4"

    return "ok", ""


def _wave5_targets(
    swings: list[_Swing], wave_index: int, cfg: ElliottWaveConfig
) -> tuple[float, float]:
    cycle_start = wave_index - (wave_index % 9)
    if cycle_start < 0 or cycle_start + 4 >= len(swings):
        return np.nan, np.nan
    p3 = swings[cycle_start + 3].price
    p4 = swings[cycle_start + 4].price
    base = abs(p3 - p4)
    if p3 > p4:
        return p4 + base * cfg.wave5_min_extension, p4 + base * cfg.wave5_max_extension
    return p4 - base * cfg.wave5_min_extension, p4 - base * cfg.wave5_max_extension


def _state(invalid: bool, warning: bool) -> str:
    if invalid:
        return "invalid"
    if warning:
        return "warning"
    return "ok"


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0 or np.isnan(denominator):
        return np.nan
    return numerator / denominator
