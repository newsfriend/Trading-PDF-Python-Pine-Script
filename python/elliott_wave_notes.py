"""State-based Elliott Wave overlay engine.

The confirmed pivot/ATR layer is only a raw market-structure provider.  Main
Elliott labels are emitted by a persistent candidate lifecycle so that a new
minor pivot cannot advance or restart the main-degree count by itself.

The source-locked candidate engine implements the P0 foundation, the core
Wave 1-5 impulse sequence, and the mandatory transition into a parallel larger
correction container (A-B-C, W-X-Y, W-X-Y-XX-Z or Triangle). Labels are
promoted only after their structure gates pass; raw pivots never advance the
main count by position or modulo arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Mapping
import numpy as np
import pandas as pd


_FIB_LEVELS = (
    (0.0, "0"),
    (0.14, "14"),
    (0.236, "236"),
    (0.382, "382"),
    (0.50, "50"),
    (0.618, "618"),
    (0.812, "812"),
    (1.0, "100"),
    (1.11, "111"),
    (1.272, "1272"),
)


@dataclass(frozen=True)
class ElliottDegreeRoute:
    key: str
    name: str
    timeframe: str
    parent: str | None
    context_parent: str | None
    pivot_length: int


ELLIOTT_DEGREE_ROUTES = (
    ElliottDegreeRoute("M", "Monthly", "M", None, None, 2),
    ElliottDegreeRoute("W", "Weekly", "W", "M", None, 3),
    ElliottDegreeRoute("D", "Daily", "D", "W", None, 5),
    ElliottDegreeRoute("288", "288 Minute", "288", "D", None, 5),
    ElliottDegreeRoute("240", "Four Hour", "240", "D", None, 5),
    ElliottDegreeRoute("60", "Hourly", "60", "240", "288", 7),
    ElliottDegreeRoute("15", "Fifteen Minute", "15", "60", None, 9),
    ElliottDegreeRoute("5", "Five Minute", "5", "15", None, 12),
    ElliottDegreeRoute("3", "Three Minute", "3", "5", None, 15),
)


@dataclass(frozen=True)
class ElliottWaveConfig:
    """Configurable values shared with ``pine/elliott_wave_notes.pine``."""

    engine_mode: str = "Candidate State"
    degree_preset: str = "Chartking Day Trading"
    degree_name: str = "Major"
    degree_timeframe: str = "D"
    important_context_mode: str = "Calendar days"
    important_lookback_days: int = 144
    pivot_left: int = 5
    pivot_right: int = 5
    max_swings: int = 120
    max_completed_cycles: int = 3
    min_swing_atr_multiple: float = 1.5
    min_swing_range_pct: float = 0.03
    degree_pivot_atr_multiple: float = 3.0
    degree_pivot_range_pct: float = 0.10
    correction_pattern: str = "A-B-C"
    show_wave4_internal: bool = True
    count_mode: str = "Validated Anchor"
    wave1_start_mode: str = "Significant degree swing"
    base_oscillator_mode: str = "Extreme or divergence"
    anchor_direction: str = "Auto"
    important_atr_length: int = 14
    important_atr_multiple: float = 1.0
    rsi_length: int = 13
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    oscillator_lookback: int = 100
    important_lookback: int = 144
    degree_retrace: float = 0.618
    wave2_minimum_mode: str = "Chartking"
    wave2_min_retrace: float = 0.236
    wave2_max_retrace: float = 0.812
    microscopic_retrace: float = 0.14
    microscopic_tolerance: float = 0.02
    wave2_max_time: float = 2.0
    wave3_min_extension: float = 1.618
    wave3_terminal_min_extension: float = 0.618
    wave3_maximum_mode: str = "Chartking 2700%"
    wave3_max_extension: float = 27.0
    wave4_minimum_mode: str = "Chartking"
    wave4_min_retrace: float = 0.236
    wave4_max_retrace: float = 0.50
    wave4_terminal_max_retrace: float = 0.618
    flat_a_min_retrace: float = 0.382
    flat_b_min_retrace: float = 0.618
    flat_b_max_retrace: float = 1.11
    wave5_min_extension: float = 1.27
    wave5_max_extension: float = 2.618
    wave5_divergence_mode: str = "Support"
    time_rule_mode: str = "Diagnostic all sources"
    hp_signal_mode: str = "Structure confirmation only"
    time_tolerance_bars: int = 8
    diagnostic_time_tolerance_ratio: float = 0.25
    w1_internal_move_counts: tuple[int, ...] = (5, 9, 13, 17, 21)


@dataclass(frozen=True)
class _Swing:
    position: int
    confirmed_position: int
    index: object
    confirmed_index: object
    price: float
    kind: int  # 1 = pivot high, -1 = pivot low
    atr: float
    macd_hist: float
    rsi: float
    macd_extreme: bool
    important_extreme: bool
    important_range: float
    important_high: float
    important_low: float
    degree_significant: bool = False
    important_high_position: int | None = None
    important_low_position: int | None = None


def compute_elliott_waves(
    candles: pd.DataFrame,
    config: ElliottWaveConfig | None = None,
    *,
    important_context: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return OHLC data with Elliott Wave labels on confirmed swing pivots."""

    cfg = config or ElliottWaveConfig()
    _validate_config(cfg)
    source = _with_indicators(
        _normalize_ohlc(candles), cfg, important_context=important_context
    )
    pivots = _detect_pivots(source, cfg)
    swings = _build_swings(pivots, cfg)

    result = source.copy()
    result["ew_raw_pivot"] = False
    result["ew_raw_side"] = np.nan
    result["ew_raw_confirmed_at"] = pd.Series(index=result.index, dtype="object")
    for swing in swings:
        result.loc[swing.index, "ew_raw_pivot"] = True
        result.loc[swing.index, "ew_raw_side"] = swing.kind
        result.loc[swing.index, "ew_raw_confirmed_at"] = swing.confirmed_index

    if cfg.engine_mode == "Candidate State":
        return _compute_candidate_state(source, swings, cfg, result)

    result["ew_pivot"] = False
    result["ew_confirmed_at"] = pd.Series(index=result.index, dtype="object")
    result["ew_label"] = pd.Series(index=result.index, dtype="object")
    result["ew_phase"] = np.nan
    result["ew_cycle"] = np.nan
    result["ew_correction_pattern"] = pd.Series(index=result.index, dtype="object")
    result["ew_rule_state"] = pd.Series(index=result.index, dtype="object")
    result["ew_rule_note"] = pd.Series(index=result.index, dtype="object")
    result["ew_start_confirmed"] = pd.Series(index=result.index, dtype="object")
    result["ew_anchor_direction"] = pd.Series(index=result.index, dtype="object")
    result["ew_anchor_important_high"] = np.nan
    result["ew_anchor_important_low"] = np.nan
    for _, fib_name in _FIB_LEVELS:
        result[f"ew_anchor_fib_{fib_name}"] = np.nan
    result["ew_wave_duration"] = np.nan
    result["ew_time_ratio"] = np.nan
    result["ew_wave5_min_target"] = np.nan
    result["ew_wave5_max_target"] = np.nan

    cycle_length = _cycle_length(cfg)
    for wave_index, swing in enumerate(swings):
        phase = _phase_for_index(swings, wave_index, cfg)
        if phase is None:
            continue
        cycle_start = wave_index - phase
        cycle = cycle_start // cycle_length
        state, note, start_confirmed, duration, time_ratio = _rule_state(
            swings, wave_index, cfg, phase, cycle_start
        )
        result.loc[swing.index, "ew_pivot"] = True
        result.loc[swing.index, "ew_confirmed_at"] = swing.confirmed_index
        result.loc[swing.index, "ew_label"] = _phase_label(phase, cfg)
        result.loc[swing.index, "ew_phase"] = phase
        result.loc[swing.index, "ew_cycle"] = cycle
        result.loc[swing.index, "ew_correction_pattern"] = cfg.correction_pattern
        result.loc[swing.index, "ew_rule_state"] = state
        result.loc[swing.index, "ew_rule_note"] = note
        result.loc[swing.index, "ew_start_confirmed"] = start_confirmed
        if 0 <= cycle_start < len(swings):
            anchor = swings[cycle_start]
            bullish_anchor = anchor.kind == -1
            result.loc[swing.index, "ew_anchor_direction"] = "bullish" if bullish_anchor else "bearish"
            result.loc[swing.index, "ew_anchor_important_high"] = anchor.important_high
            result.loc[swing.index, "ew_anchor_important_low"] = anchor.important_low
            for fib_ratio, fib_name in _FIB_LEVELS:
                result.loc[swing.index, f"ew_anchor_fib_{fib_name}"] = _anchor_fib_price(anchor, fib_ratio)
        result.loc[swing.index, "ew_wave_duration"] = duration
        result.loc[swing.index, "ew_time_ratio"] = time_ratio

        if phase == _wave4_phase(cfg):
            min_target, max_target = _wave5_targets(swings, wave_index, cfg)
            result.loc[swing.index, "ew_wave5_min_target"] = min_target
            result.loc[swing.index, "ew_wave5_max_target"] = max_target

    return result


def compute_elliott_waves_multi_degree(
    candles_by_timeframe: Mapping[str, pd.DataFrame],
    config: ElliottWaveConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """Run independent V4 counts for the locked nine-timeframe degree router."""

    missing = [
        route.timeframe
        for route in ELLIOTT_DEGREE_ROUTES
        if route.timeframe not in candles_by_timeframe
    ]
    if missing:
        raise ValueError(
            "candles_by_timeframe is missing locked routes: " + ", ".join(missing)
        )

    base_cfg = config or ElliottWaveConfig()
    results: dict[str, pd.DataFrame] = {}
    for route in ELLIOTT_DEGREE_ROUTES:
        source = candles_by_timeframe[route.timeframe].sort_index().iloc[-5000:]
        route_cfg = replace(
            base_cfg,
            degree_preset="Manual",
            degree_name=route.name,
            degree_timeframe=route.timeframe,
            pivot_left=route.pivot_length,
            pivot_right=route.pivot_length,
        )
        result = compute_elliott_waves(source, route_cfg)
        parent_alignment_series = _degree_alignment_series(
            result, results.get(route.parent), route.parent
        )
        context_alignment_series = _degree_alignment_series(
            result, results.get(route.context_parent), route.context_parent
        )
        result["ew_parent_degree"] = route.parent or ""
        result["ew_context_degree"] = route.context_parent or ""
        result["ew_parent_alignment"] = parent_alignment_series
        result["ew_context_alignment"] = context_alignment_series
        if "ew_confidence" in result:
            confidence_events = _confirmed_value_events(result, "ew_confidence")
            confirmed_confidence = pd.to_numeric(
                _event_timeline(confidence_events, result.index), errors="coerce"
            )
            route_bonus = parent_alignment_series.eq("ALIGNED").astype(float) * 5.0
            result["ew_routed_confidence"] = (
                confirmed_confidence + route_bonus
            ).clip(upper=100.0)
        parent_alignment = _latest_object_value(result, "ew_parent_alignment")
        context_alignment = _latest_object_value(result, "ew_context_alignment")
        result.attrs["elliott_degree_route"] = {
            "key": route.key,
            "name": route.name,
            "timeframe": route.timeframe,
            "parent": route.parent,
            "context_parent": route.context_parent,
            "pivot_length": route.pivot_length,
            "history_bars": len(result),
            "parent_alignment": parent_alignment,
            "context_alignment": context_alignment,
        }
        results[route.timeframe] = result
    return results


def _latest_object_value(frame: pd.DataFrame, column: str) -> str:
    if column not in frame:
        return ""
    values = frame[column].dropna()
    if values.empty:
        return ""
    return str(values.iloc[-1])


def _degree_alignment_series(
    child: pd.DataFrame,
    parent: pd.DataFrame | None,
    parent_name: str | None,
) -> pd.Series:
    """Return confirmation-safe parent alignment without backfilling history."""

    if parent_name is None:
        return pd.Series("ROOT", index=child.index, dtype="object")
    if parent is None:
        return pd.Series("PENDING", index=child.index, dtype="object")

    child_events = _confirmed_direction_events(child)
    parent_events = _confirmed_direction_events(parent)
    child_direction = _event_timeline(child_events, child.index)
    parent_direction = _event_timeline(parent_events, child.index)
    return _alignment_values(child_direction, parent_direction, child.index)


def _confirmed_direction_events(frame: pd.DataFrame) -> pd.Series:
    return _confirmed_value_events(frame, "ew_anchor_direction").astype("object")


def _confirmed_value_events(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame or "ew_confirmed_at" not in frame:
        return pd.Series(dtype="object")
    mask = frame[column].notna() & frame["ew_confirmed_at"].notna()
    if not mask.any():
        return pd.Series(dtype="object")
    events = pd.Series(
        frame.loc[mask, column].to_numpy(),
        index=pd.Index(frame.loc[mask, "ew_confirmed_at"].to_numpy()),
    )
    return events[~events.index.duplicated(keep="last")].sort_index()


def _event_timeline(events: pd.Series, index: pd.Index) -> pd.Series:
    if events.empty:
        return pd.Series("", index=index, dtype="object")
    try:
        expanded_index = events.index.union(index)
        expanded = events.reindex(expanded_index).sort_index().ffill()
        return expanded.reindex(index).fillna("").astype("object")
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Degree-route indexes and confirmation timestamps must be comparable."
        ) from exc


def _alignment_values(
    child_direction: pd.Series,
    parent_direction: pd.Series,
    index: pd.Index,
) -> pd.Series:
    child_values = child_direction.fillna("").astype(str).to_numpy()
    parent_values = parent_direction.fillna("").astype(str).to_numpy()
    values = np.full(len(index), "PENDING", dtype=object)
    ready = (child_values != "") & (parent_values != "")
    values[ready & (child_values == parent_values)] = "ALIGNED"
    values[ready & (child_values != parent_values)] = "DIVERGENT"
    return pd.Series(values, index=index, dtype="object")


def _validate_config(cfg: ElliottWaveConfig) -> None:
    valid_engine_modes = {"Candidate State", "Legacy fixed cycle"}
    if cfg.engine_mode not in valid_engine_modes:
        raise ValueError(f"engine_mode must be one of {sorted(valid_engine_modes)}")
    valid_degree_presets = {
        "Chartking Day Trading",
        "Hardik 1Y",
        "Hardik Swing",
        "Hardik Day Trading",
        "Manual",
    }
    if cfg.degree_preset not in valid_degree_presets:
        raise ValueError(f"degree_preset must be one of {sorted(valid_degree_presets)}")
    if cfg.important_context_mode not in {
        "Calendar days",
        "Source timeframe bars",
        "Legacy bars",
    }:
        raise ValueError(
            'important_context_mode must be "Calendar days", '
            '"Source timeframe bars", or "Legacy bars"'
        )
    if cfg.important_lookback_days < 1:
        raise ValueError("important_lookback_days must be at least 1 day")
    valid_oscillator_modes = {
        "Extreme or divergence",
        "Extreme only",
        "Divergence only",
        "Extreme and divergence",
        "Off",
    }
    if cfg.base_oscillator_mode not in valid_oscillator_modes:
        raise ValueError(f"base_oscillator_mode must be one of {sorted(valid_oscillator_modes)}")
    if cfg.wave2_minimum_mode not in {"Chartking", "Hardik", "Legacy 14%"}:
        raise ValueError('wave2_minimum_mode must be "Chartking", "Hardik", or "Legacy 14%"')
    if cfg.wave4_minimum_mode not in {"Chartking", "Hardik", "Extension context"}:
        raise ValueError(
            'wave4_minimum_mode must be "Chartking", "Hardik", or "Extension context"'
        )
    if cfg.wave3_maximum_mode not in {"Chartking 2700%", "Impulse 2100%"}:
        raise ValueError(
            'wave3_maximum_mode must be "Chartking 2700%" or "Impulse 2100%"'
        )
    if cfg.wave5_divergence_mode not in {"Support", "Required", "Off"}:
        raise ValueError('wave5_divergence_mode must be "Support", "Required", or "Off"')
    if cfg.time_rule_mode not in {
        "Diagnostic all sources",
        "Chartking",
        "Hardik",
        "Separate Time Analysis",
    }:
        raise ValueError("Unsupported time_rule_mode")
    if cfg.hp_signal_mode not in {
        "Structure confirmation only",
        "Disabled",
    }:
        raise ValueError("Unsupported hp_signal_mode")
    if not cfg.w1_internal_move_counts or any(
        count < 5 or count % 4 != 1 for count in cfg.w1_internal_move_counts
    ):
        raise ValueError("w1_internal_move_counts must use the 5/9/13/17/21 (+4) sequence")
    valid_patterns = {
        "A-B-C",
        "W-X-Y",
        "W-X-Y-X-Z",  # legacy display alias
        "W-X-Y-XX-Z",
        "A-B-C-D-E",
    }
    if cfg.correction_pattern not in valid_patterns:
        raise ValueError(f"correction_pattern must be one of {sorted(valid_patterns)}")
    valid_start_modes = {
        "Off",
        "Significant degree swing",
        "Important swing",
        "Important swing + oscillator",
    }
    if cfg.wave1_start_mode not in valid_start_modes:
        raise ValueError(f"wave1_start_mode must be one of {sorted(valid_start_modes)}")
    valid_count_modes = {"Validated Anchor", "All swings"}
    if cfg.count_mode not in valid_count_modes:
        raise ValueError(f"count_mode must be one of {sorted(valid_count_modes)}")
    valid_anchor_directions = {"Auto", "Bullish from important low", "Bearish from important high"}
    if cfg.anchor_direction not in valid_anchor_directions:
        raise ValueError(f"anchor_direction must be one of {sorted(valid_anchor_directions)}")
    if cfg.important_lookback < 10:
        raise ValueError("important_lookback must be at least 10 bars")
    if not 1 <= cfg.max_completed_cycles <= 3:
        raise ValueError("max_completed_cycles must be between 1 and 3")
    positive_lengths = {
        "pivot_left": cfg.pivot_left,
        "pivot_right": cfg.pivot_right,
        "max_swings": cfg.max_swings,
        "important_atr_length": cfg.important_atr_length,
        "rsi_length": cfg.rsi_length,
        "macd_fast": cfg.macd_fast,
        "macd_slow": cfg.macd_slow,
        "macd_signal": cfg.macd_signal,
        "oscillator_lookback": cfg.oscillator_lookback,
    }
    invalid_lengths = [name for name, value in positive_lengths.items() if value < 1]
    if invalid_lengths:
        raise ValueError(
            "These Elliott configuration lengths must be positive: "
            + ", ".join(invalid_lengths)
        )
    if (
        cfg.min_swing_atr_multiple < 0
        or cfg.min_swing_range_pct < 0
        or cfg.degree_pivot_atr_multiple < 0
        or cfg.degree_pivot_range_pct < 0
        or cfg.important_atr_multiple < 0
    ):
        raise ValueError("Swing and ATR thresholds cannot be negative")
    if cfg.degree_retrace <= 0:
        raise ValueError("degree_retrace must be greater than 0")
    if not 0 < cfg.wave2_min_retrace <= cfg.wave2_max_retrace < 1:
        raise ValueError("Wave 2 normal retracement must be inside (0, 1)")
    if not 0 < cfg.wave4_min_retrace <= cfg.wave4_max_retrace < 1:
        raise ValueError("Wave 4 normal retracement must be inside (0, 1)")
    if cfg.wave3_terminal_min_extension <= 0 or cfg.wave3_min_extension <= 0:
        raise ValueError("Wave 3 extension thresholds must be positive")
    if cfg.wave3_max_extension < cfg.wave3_min_extension:
        raise ValueError("Wave 3 maximum extension cannot be below its minimum")
    if not 0 <= cfg.microscopic_retrace < 1 or cfg.microscopic_tolerance < 0:
        raise ValueError("Microscopic Wave 2 thresholds are invalid")
    if cfg.wave2_max_time <= 0 or cfg.diagnostic_time_tolerance_ratio < 0:
        raise ValueError("Time thresholds must be positive/non-negative")
    if not 0 < cfg.wave4_terminal_max_retrace < 1:
        raise ValueError("wave4_terminal_max_retrace must be inside (0, 1)")
    if not 0 < cfg.flat_a_min_retrace < 1:
        raise ValueError("flat_a_min_retrace must be inside (0, 1)")
    if cfg.flat_b_min_retrace <= 0 or cfg.flat_b_max_retrace < cfg.flat_b_min_retrace:
        raise ValueError("flat_b_max_retrace must be greater than or equal to flat_b_min_retrace")
    if not 0 < cfg.wave5_min_extension <= cfg.wave5_max_extension:
        raise ValueError(
            "Wave 5 extension thresholds must be positive and ordered"
        )
    if cfg.time_tolerance_bars < 0:
        raise ValueError("time_tolerance_bars cannot be negative")


def _normalize_ohlc(candles: pd.DataFrame) -> pd.DataFrame:
    normalized = candles.copy()
    normalized_columns = [str(column).strip().lower() for column in normalized.columns]
    if len(normalized_columns) != len(set(normalized_columns)):
        raise ValueError("OHLC column names must be unique after normalization")
    normalized.columns = normalized_columns
    missing = [column for column in ("high", "low", "close") if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required OHLC columns: {missing}")
    if normalized.empty:
        raise ValueError("OHLC input must contain at least one candle")
    if normalized.index.has_duplicates:
        raise ValueError("OHLC index must not contain duplicate timestamps/labels")
    for column in ("high", "low", "close"):
        try:
            normalized[column] = pd.to_numeric(normalized[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"OHLC column {column!r} must be numeric") from exc
    values = normalized.loc[:, ["high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("OHLC values must all be finite numbers")
    invalid_range = (
        (normalized["high"] < normalized["low"])
        | (normalized["high"] < normalized["close"])
        | (normalized["low"] > normalized["close"])
    )
    if invalid_range.any():
        raise ValueError("Each OHLC candle must have a valid high/low price range")
    return normalized.sort_index()


def _with_indicators(
    source: pd.DataFrame,
    cfg: ElliottWaveConfig,
    *,
    important_context: pd.DataFrame | None = None,
) -> pd.DataFrame:
    enriched = source.copy()
    close = enriched["close"].astype(float)
    high = enriched["high"].astype(float)
    low = enriched["low"].astype(float)

    if cfg.important_context_mode == "Source timeframe bars":
        if important_context is None:
            raise ValueError(
                "important_context is required for Source timeframe bars mode"
            )
        context = _normalize_ohlc(important_context)
        if not isinstance(enriched.index, pd.DatetimeIndex) or not isinstance(
            context.index, pd.DatetimeIndex
        ):
            raise ValueError(
                "DatetimeIndex values are required for Source timeframe bars context"
            )
        context_high = context["high"].astype(float).rolling(
            cfg.important_lookback, min_periods=1
        ).max()
        context_low = context["low"].astype(float).rolling(
            cfg.important_lookback, min_periods=1
        ).min()
        context_high_time = _rolling_extreme_index(
            context["high"].astype(float), cfg.important_lookback, "max"
        )
        context_low_time = _rolling_extreme_index(
            context["low"].astype(float), cfg.important_lookback, "min"
        )
        source_is_context = enriched.index.equals(context.index)
        if not source_is_context:
            context_high = context_high.shift(1)
            context_low = context_low.shift(1)
            context_high_time = context_high_time.shift(1)
            context_low_time = context_low_time.shift(1)
        enriched["_ew_important_high"] = context_high.reindex(
            enriched.index, method="ffill"
        )
        enriched["_ew_important_low"] = context_low.reindex(
            enriched.index, method="ffill"
        )
        high_times = context_high_time.reindex(enriched.index, method="ffill")
        low_times = context_low_time.reindex(enriched.index, method="ffill")
        enriched["_ew_important_high_position"] = _timestamps_to_positions(
            enriched.index, high_times
        )
        enriched["_ew_important_low_position"] = _timestamps_to_positions(
            enriched.index, low_times
        )
    elif cfg.important_context_mode == "Calendar days":
        if not isinstance(enriched.index, pd.DatetimeIndex):
            raise ValueError(
                "A DatetimeIndex is required for Calendar days Important H/L context. "
                "Use important_context_mode='Legacy bars' only for compatibility data."
            )
        window = f"{cfg.important_lookback_days}D"
        enriched["_ew_important_high"] = high.rolling(window, min_periods=1).max()
        enriched["_ew_important_low"] = low.rolling(window, min_periods=1).min()
        high_times = _rolling_time_extreme_index(high, window, "max")
        low_times = _rolling_time_extreme_index(low, window, "min")
        enriched["_ew_important_high_position"] = _timestamps_to_positions(
            enriched.index, high_times
        )
        enriched["_ew_important_low_position"] = _timestamps_to_positions(
            enriched.index, low_times
        )
    else:
        enriched["_ew_important_high"] = high.rolling(
            cfg.important_lookback, min_periods=1
        ).max()
        enriched["_ew_important_low"] = low.rolling(
            cfg.important_lookback, min_periods=1
        ).min()
        enriched["_ew_important_high_position"] = _rolling_extreme_positions(
            high.to_numpy(dtype=float), cfg.important_lookback, "max"
        )
        enriched["_ew_important_low_position"] = _rolling_extreme_positions(
            low.to_numpy(dtype=float), cfg.important_lookback, "min"
        )
    enriched["_ew_important_range"] = (
        enriched["_ew_important_high"] - enriched["_ew_important_low"]
    )

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low).abs(), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    enriched["_ew_atr"] = _rma(true_range, cfg.important_atr_length)

    change = close.diff()
    gains = change.clip(lower=0.0)
    losses = -change.clip(upper=0.0)
    average_gain = _rma(gains, cfg.rsi_length)
    average_loss = _rma(losses, cfg.rsi_length)
    rs = average_gain / average_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.mask((average_loss == 0.0) & (average_gain > 0.0), 100.0)
    rsi = rsi.mask((average_loss == 0.0) & (average_gain == 0.0), 50.0)
    enriched["_ew_rsi"] = rsi

    macd_line = _ema(close, cfg.macd_fast) - _ema(close, cfg.macd_slow)
    signal_line = _ema(macd_line, cfg.macd_signal)
    enriched["_ew_macd_hist"] = macd_line - signal_line
    enriched["_ew_macd_lowest"] = enriched["_ew_macd_hist"] <= enriched["_ew_macd_hist"].rolling(
        cfg.oscillator_lookback, min_periods=1
    ).min()
    enriched["_ew_macd_highest"] = enriched["_ew_macd_hist"] >= enriched["_ew_macd_hist"].rolling(
        cfg.oscillator_lookback, min_periods=1
    ).max()
    return enriched


def _rolling_extreme_positions(
    values: np.ndarray, window: int, mode: str
) -> np.ndarray:
    """Return the source position of each rolling price extreme."""

    positions = np.zeros(len(values), dtype=int)
    for position in range(len(values)):
        start = max(0, position - window + 1)
        local = values[start : position + 1]
        offset = int(np.argmax(local) if mode == "max" else np.argmin(local))
        positions[position] = start + offset
    return positions


def _rolling_extreme_index(
    values: pd.Series, window: int, mode: str
) -> pd.Series:
    positions = _rolling_extreme_positions(values.to_numpy(dtype=float), window, mode)
    return pd.Series(values.index.take(positions), index=values.index, dtype="object")


def _rolling_time_extreme_index(
    values: pd.Series, window: str, mode: str
) -> pd.Series:
    outputs: list[object] = []
    for timestamp in values.index:
        start = timestamp - pd.Timedelta(window)
        sample = values.loc[start:timestamp]
        outputs.append(sample.idxmax() if mode == "max" else sample.idxmin())
    return pd.Series(outputs, index=values.index, dtype="object")


def _timestamps_to_positions(
    source_index: pd.DatetimeIndex, timestamps: pd.Series
) -> np.ndarray:
    values = np.full(len(source_index), -1, dtype=int)
    for position, timestamp in enumerate(timestamps):
        if pd.isna(timestamp):
            continue
        values[position] = max(
            0, int(source_index.searchsorted(pd.Timestamp(timestamp), side="left"))
        )
    return values


def _detect_pivots(source: pd.DataFrame, cfg: ElliottWaveConfig) -> list[_Swing]:
    highs = source["high"].astype(float).to_numpy()
    lows = source["low"].astype(float).to_numpy()
    atr = source["_ew_atr"].astype(float).to_numpy()
    macd_hist = source["_ew_macd_hist"].astype(float).to_numpy()
    rsi = source["_ew_rsi"].astype(float).to_numpy()
    macd_lowest = source["_ew_macd_lowest"].fillna(False).astype(bool).to_numpy()
    macd_highest = source["_ew_macd_highest"].fillna(False).astype(bool).to_numpy()
    context_highs = source["_ew_important_high"].astype(float).to_numpy()
    context_lows = source["_ew_important_low"].astype(float).to_numpy()
    context_ranges = source["_ew_important_range"].astype(float).to_numpy()
    context_high_positions = source["_ew_important_high_position"].astype(int).to_numpy()
    context_low_positions = source["_ew_important_low_position"].astype(int).to_numpy()
    pivots: list[_Swing] = []

    for position in range(cfg.pivot_left, len(source) - cfg.pivot_right):
        confirmed_position = position + cfg.pivot_right
        high_window = highs[position - cfg.pivot_left : position + cfg.pivot_right + 1]
        low_window = lows[position - cfg.pivot_left : position + cfg.pivot_right + 1]
        important_high = float(context_highs[position])
        important_low = float(context_lows[position])
        important_range = float(context_ranges[position])

        if not np.isnan(high_window).any() and highs[position] == np.max(high_window):
            pivots.append(
                _Swing(
                    position,
                    confirmed_position,
                    source.index[position],
                    source.index[confirmed_position],
                    float(highs[position]),
                    1,
                    float(atr[position]),
                    float(macd_hist[position]),
                    float(rsi[position]),
                    bool(macd_highest[position]),
                    bool(highs[position] >= important_high),
                    important_range,
                    important_high,
                    important_low,
                    False,
                    int(context_high_positions[position]),
                    int(context_low_positions[position]),
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
                    float(atr[position]),
                    float(macd_hist[position]),
                    float(rsi[position]),
                    bool(macd_lowest[position]),
                    bool(lows[position] <= important_low),
                    important_range,
                    important_high,
                    important_low,
                    False,
                    int(context_high_positions[position]),
                    int(context_low_positions[position]),
                )
            )

    pivots.sort(key=lambda item: (item.position, -item.kind))
    return pivots


def _build_swings(pivots: list[_Swing], cfg: ElliottWaveConfig) -> list[_Swing]:
    swings: list[_Swing] = []

    for pivot in pivots:
        if not swings:
            swings.append(replace(pivot, degree_significant=pivot.important_extreme))
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
                swings[-1] = replace(
                    pivot,
                    degree_significant=(
                        last.degree_significant or pivot.important_extreme
                    ),
                )
        elif _passes_swing_filter(pivot, last, cfg):
            degree_move = _passes_degree_filter(pivot, last, cfg)
            if not last.degree_significant and degree_move:
                swings[-1] = replace(last, degree_significant=True)
            swings.append(
                replace(
                    pivot,
                    degree_significant=pivot.important_extreme or degree_move,
                )
            )

    return swings


def _passes_swing_filter(pivot: _Swing, last: _Swing, cfg: ElliottWaveConfig) -> bool:
    distance = abs(pivot.price - last.price)
    min_by_atr = pivot.atr * cfg.min_swing_atr_multiple if np.isfinite(pivot.atr) else 0.0
    min_by_range = pivot.important_range * cfg.min_swing_range_pct if np.isfinite(pivot.important_range) else 0.0
    return distance >= max(min_by_atr, min_by_range)


def _passes_degree_filter(pivot: _Swing, last: _Swing, cfg: ElliottWaveConfig) -> bool:
    """Reject minor internal pivots without making the 144-day extreme the origin."""

    distance = abs(pivot.price - last.price)
    min_by_atr = (
        pivot.atr * cfg.degree_pivot_atr_multiple
        if np.isfinite(pivot.atr)
        else 0.0
    )
    min_by_range = (
        pivot.important_range * cfg.degree_pivot_range_pct
        if np.isfinite(pivot.important_range)
        else 0.0
    )
    return distance >= max(min_by_atr, min_by_range)


def _compute_candidate_state(
    source: pd.DataFrame,
    swings: list[_Swing],
    cfg: ElliottWaveConfig,
    result: pd.DataFrame,
) -> pd.DataFrame:
    """Apply the source-locked candidate lifecycle and core impulse engine."""

    object_columns = (
        "ew_confirmed_at",
        "ew_label",
        "ew_labels",
        "ew_display_label",
        "ew_display_labels",
        "ew_cycle_ids",
        "ew_correction_pattern",
        "ew_rule_state",
        "ew_rule_note",
        "ew_start_confirmed",
        "ew_anchor_direction",
        "ew_engine_state",
        "ew_candidate_label",
        "ew_pattern",
        "ew_subtype",
        "ew_reason_code",
        "ew_next_condition",
        "ew_degree",
        "ew_degree_timeframe",
        "ew_recount_reason",
        "ew_parent_state",
        "ew_primary_pattern",
        "ew_alternate_pattern",
        "ew_source_rule_id",
        "ew_fib_anchor",
        "ew_time_rule_mode",
        "ew_macd_state",
        "ew_internal_pattern",
        "ew_hp_signal",
        "ew_channel_type",
        "ew_target_cluster",
        "ew_fbd_candidate",
        "ew_support_evidence",
        "ew_confirmation_state",
        "ew_confirmation_label",
        "ew_confirmation_parent_state",
        "ew_confirmation_pattern",
        "ew_confirmation_reason_code",
    )
    for column in object_columns:
        result[column] = pd.Series(index=result.index, dtype="object")

    result["ew_pivot"] = False
    result["ew_phase"] = np.nan
    result["ew_cycle"] = np.nan
    result["ew_anchor_important_high"] = np.nan
    result["ew_anchor_important_low"] = np.nan
    for _, fib_name in _FIB_LEVELS:
        result[f"ew_anchor_fib_{fib_name}"] = np.nan
    result["ew_wave_duration"] = np.nan
    result["ew_time_ratio"] = np.nan
    result["ew_wave5_min_target"] = np.nan
    result["ew_wave5_max_target"] = np.nan
    result["ew_base_locked"] = False
    result["ew_base_price"] = np.nan
    result["ew_base_position"] = np.nan
    result["ew_w1_degree_progress"] = np.nan
    result["ew_internal_count"] = np.nan
    result["ew_recount_count"] = 0
    result["ew_alternate_bases"] = 0
    result["ew_fib_value"] = np.nan
    result["ew_time_value"] = np.nan
    result["ew_confidence"] = np.nan
    result["ew_target_near"] = np.nan
    result["ew_target_far"] = np.nan
    result["ew_invalidation_price"] = np.nan
    result["ew_channel_target"] = np.nan
    result["ew_confirmation_event"] = False
    result["ew_confirmation_cycle"] = np.nan
    result["ew_confirmation_recount_count"] = 0
    result["ew_confirmation_base_locked"] = False
    for label in ("point0", "wave1", "wave2", "wave3", "wave4", "wave5"):
        result[f"ew_confirmation_{label}_price"] = np.nan

    lifecycle = _run_candidate_state(swings, cfg, source)
    for event in lifecycle["events"]:
        event_index = event["index"]
        if event_index not in result.index:
            continue
        for column, value in event["values"].items():
            result.loc[event_index, column] = value
        confirmation_index = event.get("confirmed_index", event_index)
        if confirmation_index not in result.index:
            continue
        event_values = event["values"]
        result.loc[confirmation_index, "ew_confirmation_event"] = True
        result.loc[confirmation_index, "ew_confirmation_state"] = event_values.get(
            "ew_engine_state", ""
        )
        result.loc[confirmation_index, "ew_confirmation_label"] = event_values.get(
            "ew_candidate_label", ""
        )
        result.loc[
            confirmation_index, "ew_confirmation_parent_state"
        ] = event_values.get("ew_parent_state", "SEARCHING")
        result.loc[confirmation_index, "ew_confirmation_pattern"] = event_values.get(
            "ew_pattern", ""
        )
        result.loc[
            confirmation_index, "ew_confirmation_reason_code"
        ] = event_values.get("ew_reason_code", "")
        result.loc[confirmation_index, "ew_confirmation_cycle"] = int(
            event.get("cycle_id", 0)
        )
        result.loc[
            confirmation_index, "ew_confirmation_recount_count"
        ] = int(event_values.get("ew_recount_count", 0))
        result.loc[
            confirmation_index, "ew_confirmation_base_locked"
        ] = bool(event_values.get("ew_base_locked", False))
        for label in ("point0", "wave1", "wave2", "wave3", "wave4", "wave5"):
            result.loc[
                confirmation_index, f"ew_confirmation_{label}_price"
            ] = event_values.get(f"ew_locked_{label}_price", np.nan)

    active = lifecycle["active"]
    archived_cycles = list(lifecycle["completed_cycles"])
    confirmed_motives = list(lifecycle["confirmed_motives"])
    if (
        active is not None
        and str(active["parent_state"]) == "CORRECTION_CONFIRMED"
        and len(archived_cycles) >= cfg.max_completed_cycles
    ):
        archived_slots = cfg.max_completed_cycles - 1
        archived_cycles = archived_cycles[-archived_slots:] if archived_slots else []
    archived_ids = {int(cycle["cycle_id"]) for cycle in archived_cycles}
    render_cycles = [
        cycle
        for cycle in confirmed_motives
        if int(cycle["cycle_id"]) not in archived_ids
    ]
    render_cycles.extend(archived_cycles)
    if active is not None:
        active_id = int(active["cycle_id"])
        render_cycles = [
            cycle for cycle in render_cycles if int(cycle["cycle_id"]) != active_id
        ]
        render_cycles.append(active)

    for cycle in render_cycles:
        cycle_id = int(cycle["cycle_id"])
        cycle_complete = str(cycle["parent_state"]) == "CORRECTION_CONFIRMED"
        base = swings[cycle["start_idx"]]
        direction = "bullish" if cycle["bullish"] else "bearish"
        degree_name, degree_timeframe = _degree_metadata(cfg)
        common = {
            "ew_pivot": True,
            "ew_cycle": cycle_id,
            "ew_rule_state": "ok",
            "ew_start_confirmed": True,
            "ew_anchor_direction": direction,
            "ew_anchor_important_high": base.important_high,
            "ew_anchor_important_low": base.important_low,
            "ew_engine_state": "CONFIRMED",
            "ew_degree": degree_name,
            "ew_degree_timeframe": degree_timeframe,
            "ew_base_locked": True,
            "ew_base_price": base.price,
            "ew_base_position": base.position,
            "ew_w1_degree_progress": cycle["degree_progress"],
            "ew_internal_count": cycle["internal_count"],
            "ew_recount_count": lifecycle["recount_count"],
            "ew_alternate_bases": lifecycle["alternate_count"],
            "ew_parent_state": cycle["parent_state"],
            "ew_time_rule_mode": cfg.time_rule_mode,
        }
        for fib_ratio, fib_name in _FIB_LEVELS:
            common[f"ew_anchor_fib_{fib_name}"] = _anchor_fib_price(base, fib_ratio)

        phase_by_label = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "A": 6, "B": 7, "C": 8, "D": 9, "E": 10}
        for label, wave in cycle["waves"].items():
            phase = phase_by_label.get(label, 8)
            swing = swings[int(wave["swing_idx"])]
            display_label = _display_wave_label(label, str(wave["pattern"]))
            for column, value in common.items():
                result.loc[swing.index, column] = value
            result.loc[swing.index, "ew_confirmed_at"] = swing.confirmed_index
            result.loc[swing.index, "ew_phase"] = phase
            result.loc[swing.index, "ew_label"] = label
            prior_labels = result.loc[swing.index, "ew_labels"]
            label_parts = [] if pd.isna(prior_labels) else str(prior_labels).split(" / ")
            if label not in label_parts:
                label_parts.append(label)
            result.loc[swing.index, "ew_labels"] = " / ".join(label_parts)
            result.loc[swing.index, "ew_display_label"] = display_label
            prior_display_labels = result.loc[swing.index, "ew_display_labels"]
            display_parts = (
                []
                if pd.isna(prior_display_labels)
                else str(prior_display_labels).split(" / ")
            )
            if display_label not in display_parts:
                display_parts.append(display_label)
            result.loc[swing.index, "ew_display_labels"] = " / ".join(display_parts)
            prior_cycle_ids = result.loc[swing.index, "ew_cycle_ids"]
            cycle_parts = [] if pd.isna(prior_cycle_ids) else str(prior_cycle_ids).split(" / ")
            cycle_text = str(cycle_id)
            if cycle_text not in cycle_parts:
                cycle_parts.append(cycle_text)
            result.loc[swing.index, "ew_cycle_ids"] = " / ".join(cycle_parts)
            result.loc[swing.index, "ew_candidate_label"] = label
            result.loc[swing.index, "ew_pattern"] = wave["pattern"]
            result.loc[swing.index, "ew_subtype"] = wave["subtype"]
            result.loc[swing.index, "ew_reason_code"] = wave["reason_code"]
            result.loc[swing.index, "ew_source_rule_id"] = wave["source_rule_id"]
            result.loc[swing.index, "ew_rule_note"] = wave["note"]
            result.loc[swing.index, "ew_next_condition"] = cycle["next_condition"]
            result.loc[swing.index, "ew_correction_pattern"] = wave.get("pattern", "")
            result.loc[swing.index, "ew_primary_pattern"] = wave.get("pattern", "")
            result.loc[swing.index, "ew_alternate_pattern"] = wave.get("alternate", "")
            result.loc[swing.index, "ew_fib_anchor"] = wave.get("fib_anchor", "")
            result.loc[swing.index, "ew_fib_value"] = wave.get("fib_value", np.nan)
            result.loc[swing.index, "ew_time_value"] = wave.get("time_value", np.nan)
            result.loc[swing.index, "ew_macd_state"] = wave.get("macd_state", "")
            result.loc[swing.index, "ew_internal_pattern"] = wave.get(
                "internal_pattern", ""
            )
            result.loc[swing.index, "ew_internal_count"] = wave.get(
                "internal_count", np.nan
            )
            result.loc[swing.index, "ew_hp_signal"] = wave.get("hp_signal", "")
            result.loc[swing.index, "ew_confidence"] = wave.get("confidence", np.nan)
            result.loc[swing.index, "ew_target_near"] = wave.get("target_near", np.nan)
            result.loc[swing.index, "ew_target_far"] = wave.get("target_far", np.nan)
            result.loc[swing.index, "ew_invalidation_price"] = wave.get(
                "invalidation_price", np.nan
            )
            result.loc[swing.index, "ew_channel_type"] = wave.get(
                "channel_type", ""
            )
            result.loc[swing.index, "ew_channel_target"] = wave.get(
                "channel_target", np.nan
            )
            result.loc[swing.index, "ew_target_cluster"] = wave.get(
                "target_cluster", ""
            )
            result.loc[swing.index, "ew_fbd_candidate"] = wave.get(
                "fbd_candidate", ""
            )
            result.loc[swing.index, "ew_support_evidence"] = wave.get(
                "support_evidence", ""
            )
            if cycle_complete:
                result.loc[swing.index, "ew_engine_state"] = "CONFIRMED"

    completed_cycle_count = int(lifecycle["completed_cycle_total"])
    if active is not None and str(active["parent_state"]) == "CORRECTION_CONFIRMED":
        completed_cycle_count += 1
    result.attrs["elliott_wave_state"] = {
        "engine": "Candidate State",
        "phase": "V4.0 motive and larger-correction sequence",
        "state": active["parent_state"] if active is not None else lifecycle["final_state"],
        "base_locked": active is not None,
        "confirmed_labels": list(active["waves"].keys()) if active is not None else [],
        "completed_cycle_count": completed_cycle_count,
        "completed_cycle_ids": [
            int(cycle["cycle_id"]) for cycle in archived_cycles
        ],
        "recount_count": lifecycle["recount_count"],
        "alternate_base_count": lifecycle["alternate_count"],
        "last_reason_code": lifecycle["last_reason_code"],
        "pending_modules": [
            "milestone-3 TradingView compile and chart replay",
            "milestone-3 candle parity and performance evidence",
            "milestone-3 client datasets and backtesting acceptance",
        ],
    }
    return result


def _degree_metadata(cfg: ElliottWaveConfig) -> tuple[str, str]:
    if cfg.degree_preset == "Hardik 1Y":
        return "Primary", "M"
    if cfg.degree_preset == "Hardik Swing":
        return "Intermediate", "D"
    if cfg.degree_preset in {"Chartking Day Trading", "Hardik Day Trading"}:
        return "Major", "D"
    return cfg.degree_name, cfg.degree_timeframe


def _start_developing_wave1(
    candidate: dict[str, object], cycle_id: int
) -> tuple[dict[str, object], dict[str, object]]:
    """Lock Point 0 at the closed development event without inventing W1."""

    active = dict(candidate)
    active.update(
        {
            "cycle_id": cycle_id,
            "last_checked_position": int(candidate["development_position"]),
            "parent_state": "W1_FORMING",
            "next_condition": (
                "Need a completed 5/9/13/17/21 Wave-1 or permitted "
                "Leading Diagonal terminal."
            ),
            "waves": {
                "0": _make_wave_record(
                    swing_idx=int(candidate["start_idx"]),
                    pattern="Base",
                    subtype="LOCKED_BASE",
                    reason_code="BASE_LOCKED",
                    source_rule_id="V4-P7-W1-DEVELOPMENT",
                    note=(
                        "Significant Point 0 locked by the closed 61.8% "
                        "degree-development and Wave-1 time event."
                    ),
                )
            },
        }
    )
    event = {
        "index": candidate["development_index"],
        "confirmed_index": candidate["development_index"],
        "cycle_id": cycle_id,
        "values": {
            "ew_engine_state": "FORMING",
            "ew_candidate_label": "1?",
            "ew_pattern": "Motive",
            "ew_subtype": "W1_DEVELOPED",
            "ew_reason_code": "W1_DEVELOPED",
            "ew_rule_state": "forming",
            "ew_rule_note": (
                "Point 0 locked after the closed 61.8% degree-development "
                "event; Wave 1 awaits a confirmed terminal pivot."
            ),
            "ew_next_condition": active["next_condition"],
            "ew_parent_state": "W1_FORMING",
            "ew_source_rule_id": "V4-P7-W1-DEVELOPMENT",
            "ew_base_locked": True,
            "ew_base_price": candidate["base_price"],
            "ew_base_position": candidate["base_position"],
            "ew_w1_degree_progress": candidate["degree_progress"],
            "ew_fib_value": candidate["development_level"],
            "ew_time_value": candidate["w1_time_ratio"],
            "ew_locked_point0_price": candidate["base_price"],
            "ew_locked_wave1_price": np.nan,
            "ew_locked_wave2_price": np.nan,
            "ew_locked_wave3_price": np.nan,
            "ew_locked_wave4_price": np.nan,
            "ew_locked_wave5_price": np.nan,
        },
    }
    return active, event


def _confirm_developing_wave1(
    active: dict[str, object], candidate: dict[str, object]
) -> None:
    active.update(candidate)
    active["parent_state"] = "W2_CORRECTION_CONTAINER"
    active["next_condition"] = (
        "Need a valid W2 correction completion while Point 0 remains intact."
    )
    active["waves"]["1"] = _make_wave_record(
        swing_idx=int(candidate["end_idx"]),
        pattern=str(candidate["pattern"]),
        subtype=str(candidate["subtype"]),
        reason_code="W1_CONFIRMED",
        source_rule_id="V4-P7-W1-COMPLETION",
        note=str(candidate["note"]),
        fib_anchor="Important H/L",
        fib_value=float(candidate["degree_progress"]),
        time_value=float(candidate["w1_time_ratio"]),
        internal_pattern=str(candidate["internal_pattern"]),
        internal_count=int(candidate["internal_count"]),
    )


def _run_candidate_state(
    swings: list[_Swing],
    cfg: ElliottWaveConfig,
    source: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Return deterministic state transitions for the core impulse engine."""

    events: list[dict[str, object]] = []
    active: dict[str, object] | None = None
    completed_cycles: list[dict[str, object]] = []
    confirmed_motives: list[dict[str, object]] = []
    next_cycle_id = 0
    search_floor = -1
    recount_count = 0
    alternate_count = 0
    last_reason_code = "SEARCHING_FOR_BASE"

    ordered_indices = sorted(
        range(len(swings)), key=lambda index: swings[index].confirmed_position
    )
    processed: list[int] = []

    for swing_index in ordered_indices:
        swing = swings[swing_index]
        if active is not None and str(active["parent_state"]) == "CORRECTION_CONFIRMED":
            completed_cycles.append(_snapshot_completed_cycle(active))
            next_cycle_id = int(active["cycle_id"]) + 1
            completed_cycles = completed_cycles[-cfg.max_completed_cycles :]
            terminal_idx = int(list(active["waves"].values())[-1]["swing_idx"])
            search_floor = swings[terminal_idx].position
            active = None

        if active is not None:
            degree_floor = _active_degree_window_floor(
                active, swings, swing.confirmed_position, cfg, source
            )
            if degree_floor is not None:
                recount_count += 1
                last_reason_code = "ACTIVE_DEGREE_WINDOW_EXPIRED"
                events.append(
                    {
                        "index": swing.confirmed_index,
                        "confirmed_index": swing.confirmed_index,
                        "cycle_id": int(active["cycle_id"]),
                        "values": {
                            "ew_engine_state": "INVALID",
                            "ew_rule_state": "invalid",
                            "ew_rule_note": (
                                "Point 0 left the configured Important H/L "
                                "context; release the stale degree count."
                            ),
                            "ew_reason_code": last_reason_code,
                            "ew_recount_reason": last_reason_code,
                            "ew_next_condition": (
                                "Search for a qualified Point 0 inside the "
                                "current degree window."
                            ),
                            "ew_recount_count": recount_count,
                            "ew_base_locked": False,
                            **_empty_locked_wave_event_values(),
                        },
                    }
                )
                search_floor = degree_floor
                active = None

        if active is not None and _origin_protection_active(str(active["parent_state"])):
            break_position = _origin_break_position(
                source,
                active,
                swings,
                int(active["last_checked_position"]) + 1,
                swing.confirmed_position,
            )
            if break_position is not None:
                break_index = (
                    source.index[break_position]
                    if source is not None
                    else swing.index
                )
                recount_count += 1
                last_reason_code = "W2_ORIGIN_BREAK"
                events.append(
                    {
                        "index": break_index,
                        "confirmed_index": break_index,
                        "cycle_id": int(active["cycle_id"]),
                        "values": {
                            "ew_engine_state": "INVALID",
                            "ew_rule_state": "invalid",
                            "ew_rule_note": "Hard invalidation: price crossed locked Point 0.",
                            "ew_reason_code": last_reason_code,
                            "ew_recount_reason": last_reason_code,
                            "ew_next_condition": "Release the count and search for a new qualified base.",
                            "ew_recount_count": recount_count,
                            "ew_base_locked": False,
                            **_empty_locked_wave_event_values(),
                        },
                    }
                )
                search_floor = break_position
                active = None

        processed.append(swing_index)
        started_wave1 = False
        if active is None:
            developed = _best_developed_base(
                swings,
                processed,
                swing.confirmed_position,
                search_floor,
                cfg,
                source,
            )
            if developed is not None:
                active, development_event = _start_developing_wave1(
                    developed, next_cycle_id
                )
                development_event["values"]["ew_recount_count"] = recount_count
                events.append(development_event)
                last_reason_code = "W1_DEVELOPED"
                started_wave1 = True

        if active is not None and str(active["parent_state"]) == "W1_FORMING":
            candidate = _candidate_ending_at(
                swings,
                processed,
                swing_index,
                search_floor,
                cfg,
                source,
                locked_start_idx=int(active["start_idx"]),
            )
            if candidate is not None:
                _confirm_developing_wave1(active, candidate)
                active["last_checked_position"] = swing.confirmed_position
                last_reason_code = "W1_CONFIRMED"
                events.append(
                    {
                        "index": swing.index,
                        "confirmed_index": swing.confirmed_index,
                        "cycle_id": int(active["cycle_id"]),
                        "values": {
                            "ew_engine_state": "CONFIRMED",
                            "ew_candidate_label": "1",
                            "ew_pattern": candidate["pattern"],
                            "ew_subtype": active["waves"]["1"]["subtype"],
                            "ew_reason_code": last_reason_code,
                            "ew_rule_state": "ok",
                            "ew_rule_note": candidate["note"],
                            "ew_next_condition": active["next_condition"],
                            "ew_parent_state": active["parent_state"],
                            "ew_source_rule_id": "V4-P7-W1-COMPLETION",
                            "ew_base_locked": True,
                            "ew_base_price": candidate["base_price"],
                            "ew_base_position": candidate["base_position"],
                            "ew_w1_degree_progress": candidate["degree_progress"],
                            "ew_internal_count": candidate["internal_count"],
                            "ew_recount_count": recount_count,
                            **_locked_wave_event_values(active, swings),
                        },
                    }
                )
            elif not started_wave1:
                events.append(
                    {
                        "index": swing.index,
                        "confirmed_index": swing.confirmed_index,
                        "cycle_id": next_cycle_id,
                        "values": {
                            "ew_engine_state": "FORMING",
                            "ew_candidate_label": "1?",
                            "ew_pattern": "Motive",
                            "ew_subtype": "W1_DEVELOPED",
                            "ew_reason_code": "W1_AWAITING_TERMINAL",
                            "ew_rule_state": "forming",
                            "ew_rule_note": "Point 0 is locked; no permitted Wave-1 terminal is confirmed yet.",
                            "ew_next_condition": active["next_condition"],
                            "ew_parent_state": "W1_FORMING",
                            "ew_recount_count": recount_count,
                            "ew_base_locked": True,
                            "ew_base_price": active["base_price"],
                            "ew_base_position": active["base_position"],
                            "ew_w1_degree_progress": active["degree_progress"],
                            **_locked_wave_event_values(active, swings),
                        },
                    }
                )

        if active is None:
            events.append(
                {
                    "index": swing.index,
                    "confirmed_index": swing.confirmed_index,
                    "cycle_id": next_cycle_id,
                    "values": {
                        "ew_engine_state": "SEARCHING",
                        "ew_reason_code": "SEARCHING_FOR_BASE",
                        "ew_next_condition": "Wait for a qualified base and a 5/9/13/17/21-move Wave 1 candidate.",
                        "ew_recount_count": recount_count,
                        "ew_base_locked": False,
                        **_empty_locked_wave_event_values(),
                    },
                }
            )
        elif str(active["parent_state"]) != "W1_FORMING":
            active["last_checked_position"] = swing.confirmed_position
            if swing_index != active["end_idx"]:
                base = swings[int(active["start_idx"])]
                same_as_base = swing.kind == base.kind
                alternate = bool(
                    same_as_base
                    and swing.important_extreme
                    and _oscillator_evidence(swings, swing_index, active["bullish"], cfg)[0]
                )
                transition = _advance_impulse_state(
                    active, swings, swing_index, cfg, source=source
                )
                if transition["reason_code"] == "W5_CONFIRMED":
                    confirmed_motives = [
                        cycle
                        for cycle in confirmed_motives
                        if int(cycle["cycle_id"]) != int(active["cycle_id"])
                    ]
                    confirmed_motives.append(_snapshot_completed_cycle(active))
                    confirmed_motives = confirmed_motives[-cfg.max_completed_cycles :]
                if alternate and transition["status"] != "CONFIRMED":
                    alternate_count += 1
                    transition["alternate_pattern"] = "Alternate base"
                    if not transition["candidate_label"]:
                        transition["candidate_label"] = "Alt 0"
                last_reason_code = str(transition["reason_code"])
                events.append(
                    {
                        "index": swing.index,
                        "confirmed_index": swing.confirmed_index,
                        "cycle_id": int(active["cycle_id"]),
                        "values": {
                            "ew_engine_state": transition["status"],
                            "ew_candidate_label": transition["candidate_label"],
                            "ew_pattern": transition["pattern"],
                            "ew_subtype": transition["subtype"],
                            "ew_reason_code": transition["reason_code"],
                            "ew_rule_state": (
                                "ok"
                                if transition["status"] == "CONFIRMED"
                                else "invalid"
                                if transition["status"] == "INVALID"
                                else "pending"
                            ),
                            "ew_rule_note": transition["note"],
                            "ew_next_condition": transition["next_condition"],
                            "ew_parent_state": active["parent_state"],
                            "ew_primary_pattern": transition["pattern"],
                            "ew_alternate_pattern": transition["alternate_pattern"],
                            "ew_source_rule_id": transition["source_rule_id"],
                            "ew_fib_anchor": transition["fib_anchor"],
                            "ew_fib_value": transition["fib_value"],
                            "ew_time_rule_mode": cfg.time_rule_mode,
                            "ew_time_value": transition["time_value"],
                            "ew_macd_state": transition["macd_state"],
                            "ew_internal_pattern": transition["internal_pattern"],
                            "ew_internal_count": transition["internal_count"],
                            "ew_hp_signal": transition["hp_signal"],
                            "ew_confidence": transition["confidence"],
                            "ew_channel_type": transition["channel_type"],
                            "ew_channel_target": transition["channel_target"],
                            "ew_target_cluster": transition["target_cluster"],
                            "ew_fbd_candidate": transition["fbd_candidate"],
                            "ew_support_evidence": transition["support_evidence"],
                            "ew_base_locked": True,
                            "ew_base_price": base.price,
                            "ew_base_position": base.position,
                            "ew_recount_count": recount_count,
                            "ew_alternate_bases": alternate_count,
                            **_locked_wave_event_values(active, swings),
                        },
                    }
                )

    if active is None and source is not None and processed:
        developed = _best_developed_base(
            swings,
            processed,
            len(source) - 1,
            search_floor,
            cfg,
            source,
        )
        if developed is not None:
            active, development_event = _start_developing_wave1(
                developed, next_cycle_id
            )
            development_event["values"]["ew_recount_count"] = recount_count
            events.append(development_event)
            last_reason_code = "W1_DEVELOPED"

    if (
        active is not None
        and source is not None
        and _origin_protection_active(str(active["parent_state"]))
    ):
        tail_break = _origin_break_position(
            source,
            active,
            swings,
            int(active["last_checked_position"]) + 1,
            len(source) - 1,
        )
        if tail_break is not None:
            recount_count += 1
            last_reason_code = "W2_ORIGIN_BREAK"
            events.append(
                {
                    "index": source.index[tail_break],
                    "confirmed_index": source.index[tail_break],
                    "cycle_id": int(active["cycle_id"]),
                    "values": {
                        "ew_engine_state": "INVALID",
                        "ew_rule_state": "invalid",
                        "ew_rule_note": "Hard invalidation: price crossed locked Point 0.",
                        "ew_reason_code": last_reason_code,
                        "ew_recount_reason": last_reason_code,
                        "ew_next_condition": "Release the count and search for a new qualified base.",
                        "ew_recount_count": recount_count,
                        "ew_base_locked": False,
                        **_empty_locked_wave_event_values(),
                    },
                }
            )
            active = None

    return {
        "active": active,
        "completed_cycles": completed_cycles,
        "confirmed_motives": confirmed_motives,
        "completed_cycle_total": next_cycle_id,
        "events": events,
        "recount_count": recount_count,
        "alternate_count": alternate_count,
        "final_state": "SEARCHING" if active is None else str(active["parent_state"]),
        "last_reason_code": last_reason_code,
    }


def _snapshot_completed_cycle(active: dict[str, object]) -> dict[str, object]:
    """Copy a locked cycle before the lifecycle searches for its successor."""

    snapshot = dict(active)
    snapshot["waves"] = {
        str(label): dict(wave)
        for label, wave in dict(active["waves"]).items()
    }
    return snapshot


def _empty_locked_wave_event_values() -> dict[str, float]:
    return {
        f"ew_locked_{label}_price": np.nan
        for label in ("point0", "wave1", "wave2", "wave3", "wave4", "wave5")
    }


def _locked_wave_event_values(
    active: dict[str, object], swings: list[_Swing]
) -> dict[str, object]:
    values: dict[str, object] = {"ew_base_locked": True}
    output_names = {
        "0": "point0",
        "1": "wave1",
        "2": "wave2",
        "3": "wave3",
        "4": "wave4",
        "5": "wave5",
    }
    waves = dict(active["waves"])
    for wave_label, output_name in output_names.items():
        wave = waves.get(wave_label)
        values[f"ew_locked_{output_name}_price"] = (
            swings[int(wave["swing_idx"])].price if wave is not None else np.nan
        )
    return values


def _correction_terminal_label(pattern: str) -> str:
    """Return the child correction terminal shown beside a parent W2/W4."""

    if "W-X-Y-XX-Z" in pattern:
        return "Z"
    if "W-X-Y" in pattern:
        return "Y"
    if "Triangle" in pattern:
        return "E"
    return "C"


def _display_wave_label(label: str, pattern: str) -> str:
    """Keep machine labels stable while matching the reference chart grammar."""

    if label in {"2", "4"}:
        return f"{label}\n({_correction_terminal_label(pattern)})"
    if label not in {"0", "1", "2", "3", "4", "5"}:
        return f"({label})"
    return label


def _make_wave_record(
    *,
    swing_idx: int,
    pattern: str,
    subtype: str,
    reason_code: str,
    source_rule_id: str,
    note: str,
    fib_anchor: str = "",
    fib_value: float = np.nan,
    time_value: float = np.nan,
    macd_state: str = "",
    internal_pattern: str = "",
    internal_count: int | float = np.nan,
    alternate: str = "",
    hp_signal: str = "",
    confidence: float = np.nan,
    target_near: float = np.nan,
    target_far: float = np.nan,
    invalidation_price: float = np.nan,
    channel_type: str = "",
    channel_target: float = np.nan,
    target_cluster: str = "",
    fbd_candidate: str = "",
    support_evidence: str = "",
) -> dict[str, object]:
    return {
        "swing_idx": swing_idx,
        "pattern": pattern,
        "subtype": subtype,
        "reason_code": reason_code,
        "source_rule_id": source_rule_id,
        "note": note,
        "fib_anchor": fib_anchor,
        "fib_value": fib_value,
        "time_value": time_value,
        "macd_state": macd_state,
        "internal_pattern": internal_pattern,
        "internal_count": internal_count,
        "alternate": alternate,
        "hp_signal": hp_signal,
        "confidence": confidence,
        "target_near": target_near,
        "target_far": target_far,
        "invalidation_price": invalidation_price,
        "channel_type": channel_type,
        "channel_target": channel_target,
        "target_cluster": target_cluster,
        "fbd_candidate": fbd_candidate,
        "support_evidence": support_evidence,
    }


def _origin_protection_active(parent_state: str) -> bool:
    """Point 0 is a hard invalidation only while the motive count is forming."""

    return parent_state in {
        "W1_FORMING",
        "W2_CORRECTION_CONTAINER",
        "W3_FORMING",
        "W4_CORRECTION_CONTAINER",
        "W5_FORMING",
    }


def _active_degree_window_floor(
    active: dict[str, object],
    swings: list[_Swing],
    through_position: int,
    cfg: ElliottWaveConfig,
    source: pd.DataFrame | None,
) -> int | None:
    """Return a new search floor when Point 0 leaves its degree context."""

    base_position = swings[int(active["start_idx"])].position
    if cfg.important_context_mode == "Calendar days" and source is not None:
        if not isinstance(source.index, pd.DatetimeIndex):
            return None
        current_position = min(through_position, len(source) - 1)
        current_time = source.index[current_position]
        base_time = source.index[base_position]
        window = pd.Timedelta(days=cfg.important_lookback_days)
        if current_time - base_time <= window:
            return None
        return int(source.index.searchsorted(current_time - window, side="left"))

    if through_position - base_position <= cfg.important_lookback_days:
        return None
    return max(0, through_position - cfg.important_lookback_days)


def _larger_correction_candidate_label(move_count: int, cfg: ElliottWaveConfig) -> str:
    """Return only a developing label; actual A/B/C labels lock on completion."""

    minimum_a = min(cfg.w1_internal_move_counts)
    minimum_b = 3
    if move_count < minimum_a:
        return "A?"
    if move_count < minimum_a + minimum_b:
        return "B?"
    return "C?"


def _transition(
    *,
    status: str = "FORMING",
    candidate_label: str = "",
    pattern: str = "",
    subtype: str = "",
    reason_code: str,
    note: str,
    next_condition: str,
    source_rule_id: str,
    alternate_pattern: str = "",
    fib_anchor: str = "",
    fib_value: float = np.nan,
    time_value: float = np.nan,
    macd_state: str = "",
    internal_pattern: str = "",
    internal_count: int | float = np.nan,
    hp_signal: str = "",
    confidence: float = np.nan,
    channel_type: str = "",
    channel_target: float = np.nan,
    target_cluster: str = "",
    fbd_candidate: str = "",
    support_evidence: str = "",
) -> dict[str, object]:
    return locals()


def _advance_impulse_state(
    active: dict[str, object],
    swings: list[_Swing],
    end_idx: int,
    cfg: ElliottWaveConfig,
    *,
    source: pd.DataFrame | None = None,
) -> dict[str, object]:
    state = str(active["parent_state"])
    bullish = bool(active["bullish"])
    waves = active["waves"]

    if state == "W2_CORRECTION_CONTAINER":
        start_idx = int(waves["1"]["swing_idx"])
        correction = _evaluate_correction(
            swings, start_idx, end_idx, cfg, source=source
        )
        terminal_idx = int(correction.get("terminal_index", end_idx))
        p0 = swings[int(waves["0"]["swing_idx"])]
        p1 = swings[start_idx]
        p2 = swings[terminal_idx]
        correct_side = p2.kind == (-1 if bullish else 1)
        retrace = _directional_retrace(p0.price, p1.price, p2.price, bullish)
        time_ratio = _duration_ratio(p1, p2, p0, p1)
        time_gate = _matches_time_window(
            p2.position - p1.position,
            (p1.position - p0.position,),
            (0.25, 0.50, 1.0, 2.0),
            cfg.time_tolerance_bars,
        )
        microscopic = bool(
            np.isfinite(retrace)
            and abs(retrace - cfg.microscopic_retrace) <= cfg.microscopic_tolerance
        )
        normal = bool(
            np.isfinite(retrace)
            and _w2_minimum(cfg) <= retrace <= cfg.wave2_max_retrace
        )
        deep = bool(np.isfinite(retrace) and 0.618 <= retrace <= 0.812)
        flat_a_pass = _flat_a_minimum_pass(
            correction, swings, start_idx, abs(p1.price - p0.price), cfg
        )
        subtype = "W2_MICROSCOPIC" if microscopic else "W2_NORMAL" if normal else "W2_OUTSIDE_NORMAL"
        hp_signal = (
            "HP BUY ELIGIBLE" if bullish else "HP SELL ELIGIBLE"
        ) if deep and correction["confirmed"] and cfg.hp_signal_mode != "Disabled" else ""

        if (
            correct_side
            and correction["confirmed"]
            and flat_a_pass
            and (normal or microscopic)
            and time_gate
        ):
            confidence = 80.0 + (10.0 if hp_signal else 0.0) + (
                10.0 if correction.get("target_cluster") else 0.0
            )
            record = _make_wave_record(
                swing_idx=terminal_idx,
                pattern=str(correction["primary"]),
                subtype=subtype,
                reason_code="W2_CONFIRMED",
                source_rule_id="V3-P24-25-W2",
                note=(
                    f"Wave 2 {correction['primary']} completed; retracement={retrace:.2%}; "
                    f"B={correction['b_ratio']:.2%}; V4 time gate=PASS."
                ),
                fib_anchor="P0-P1 retracement",
                fib_value=retrace,
                time_value=time_ratio,
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
                alternate=str(correction["alternate"]),
                hp_signal=hp_signal,
                confidence=confidence,
                channel_type=str(correction.get("channel_type", "")),
                channel_target=float(correction.get("channel_target", np.nan)),
                target_cluster=str(correction.get("target_cluster", "")),
                support_evidence="HP_STRUCTURE_CONFIRMED" if hp_signal else "",
            )
            waves["2"] = record
            active["parent_state"] = "W3_FORMING"
            active["next_condition"] = "Need a 5/9/13/17/21-move W3 candidate and trending/terminal classification."
            return _transition(
                status="CONFIRMED",
                candidate_label="2",
                pattern=str(correction["primary"]),
                subtype=subtype,
                reason_code="W2_CONFIRMED",
                note=str(record["note"]),
                next_condition=active["next_condition"],
                source_rule_id="V3-P24-25-W2",
                alternate_pattern=str(correction["alternate"]),
                fib_anchor="P0-P1 retracement",
                fib_value=retrace,
                time_value=time_ratio,
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
                hp_signal=hp_signal,
                confidence=confidence,
                channel_type=str(correction.get("channel_type", "")),
                channel_target=float(correction.get("channel_target", np.nan)),
                target_cluster=str(correction.get("target_cluster", "")),
                support_evidence="HP_STRUCTURE_CONFIRMED" if hp_signal else "",
            )

        reason = (
            "W2_TIME_GATE_FAIL"
            if correction["confirmed"] and flat_a_pass and (normal or microscopic) and not time_gate
            else "FLAT_A_LT_38_2"
            if correction["confirmed"] and not flat_a_pass
            else str(correction["reason_code"])
            if not correction["confirmed"]
            else "W2_RETRACE_OUTSIDE_NORMAL"
        )
        return _transition(
            candidate_label="2?" if correct_side else "",
            pattern=str(correction["primary"]),
            subtype=subtype,
            reason_code=reason,
            note=(
                f"Wave 2 correction container: retracement={retrace:.2%}; "
                f"{correction['note']}"
            ),
            next_condition="Need a complete Zig-Zag/Flat child and an approved W2 price context.",
            source_rule_id="V3-P24-25-W2",
            alternate_pattern=str(correction["alternate"]),
            fib_anchor="P0-P1 retracement",
            fib_value=retrace,
            time_value=time_ratio,
            internal_pattern=str(correction["internal_pattern"]),
            internal_count=int(correction["internal_count"]),
            hp_signal=hp_signal,
        )

    if state == "W3_FORMING":
        p0 = swings[int(waves["0"]["swing_idx"])]
        p1 = swings[int(waves["1"]["swing_idx"])]
        p2 = swings[int(waves["2"]["swing_idx"])]
        p3 = swings[end_idx]
        internal_count = end_idx - int(waves["2"]["swing_idx"])
        correct_side = p3.kind == (1 if bullish else -1)
        internal_valid = internal_count in cfg.w1_internal_move_counts and correct_side
        ratio = _safe_ratio(abs(p3.price - p2.price), abs(p1.price - p0.price))
        terminal_overlap = _internal_four_overlaps_one(
            swings, int(waves["2"]["swing_idx"]), end_idx, bullish
        )
        trending = internal_valid and ratio >= cfg.wave3_min_extension
        terminal = bool(
            internal_valid
            and cfg.wave3_terminal_min_extension <= ratio < cfg.wave3_min_extension
            and terminal_overlap
        )
        max_pass = np.isfinite(ratio) and ratio <= _w3_maximum(cfg)
        macd_state = "W3 MOMENTUM SUPPORT" if p3.macd_extreme else "W3 MOMENTUM NOT EXTREME"
        if (trending or terminal) and max_pass:
            w1_duration = p1.position - p0.position
            w2_duration = p2.position - p1.position
            w3_duration = p3.position - p2.position
            time_gate = _matches_time_window(
                w3_duration,
                (w1_duration + w2_duration,),
                (0.50, 1.0),
                cfg.time_tolerance_bars,
            )
            if not time_gate:
                return _transition(
                    candidate_label="3?",
                    pattern="Motive",
                    subtype="W3_TIME_PENDING",
                    reason_code="W3_TIME_GATE_FAIL",
                    note=f"Wave 3 structure passes but duration {w3_duration} misses the V4 time windows.",
                    next_condition="Wait for a valid (W1+W2)/2 or W1+W2 time window.",
                    source_rule_id="V4-C06-W3-TIME",
                    fib_anchor="P0-P1 projected from P2",
                    fib_value=ratio,
                    macd_state=macd_state,
                    internal_pattern="5/9/13/17/21-move impulse",
                    internal_count=internal_count,
                )
            subtype = "W3_TRENDING" if trending else "W3_TERMINAL"
            if internal_count > 5:
                subtype += "_EXTENDED"
            time_ratio = _duration_ratio(p2, p3, p0, p1)
            lower_degree_w4 = swings[end_idx - 1]
            lower_tolerance = (
                0.25 * lower_degree_w4.atr
                if np.isfinite(lower_degree_w4.atr)
                else 0.0
            )
            confidence = 90.0 if p3.macd_extreme else 80.0
            record = _make_wave_record(
                swing_idx=end_idx,
                pattern="Motive",
                subtype=subtype,
                reason_code="W3_CONFIRMED",
                source_rule_id="V3-P25-26-W3",
                note=f"{subtype} confirmed at {ratio:.2%} of Wave 1.",
                fib_anchor="P0-P1 projected from P2",
                fib_value=ratio,
                time_value=time_ratio,
                macd_state=macd_state,
                internal_pattern="5/9/13/17/21-move impulse",
                internal_count=internal_count,
                confidence=confidence,
                target_near=lower_degree_w4.price - lower_tolerance,
                target_far=lower_degree_w4.price + lower_tolerance,
                support_evidence="LOWER_DEGREE_W4_ZONE_0_25_ATR",
            )
            waves["3"] = record
            active["parent_state"] = "W4_CORRECTION_CONTAINER"
            active["next_condition"] = "Need a completed W4 correction; W5 is blocked until then."
            return _transition(
                status="CONFIRMED",
                candidate_label="3",
                pattern="Motive",
                subtype=subtype,
                reason_code="W3_CONFIRMED",
                note=str(record["note"]),
                next_condition=active["next_condition"],
                source_rule_id="V3-P25-26-W3",
                fib_anchor="P0-P1 projected from P2",
                fib_value=ratio,
                time_value=time_ratio,
                macd_state=macd_state,
                internal_pattern="5/9/13/17/21-move impulse",
                internal_count=internal_count,
                confidence=confidence,
                support_evidence="LOWER_DEGREE_W4_ZONE_0_25_ATR",
            )
        reason = (
            "W3_INTERNAL_FAIL"
            if not internal_valid
            else "W3_SOURCE_MAX_FAIL"
            if not max_pass
            else "W3_BELOW_TRENDING_MIN"
        )
        return _transition(
            candidate_label="3?" if correct_side else "",
            pattern="Motive",
            subtype="TERMINAL_CANDIDATE" if terminal_overlap else "TRENDING_CANDIDATE",
            reason_code=reason,
            note=f"Wave 3 forming: extension={ratio:.2%}, internal moves={internal_count}.",
            next_condition="Need approved internal count plus trending >=161.8% or a valid terminal structure.",
            source_rule_id="V3-P25-26-W3",
            fib_anchor="P0-P1 projected from P2",
            fib_value=ratio,
            macd_state=macd_state,
            internal_pattern="Impulse candidate",
            internal_count=internal_count,
        )

    if state == "W4_CORRECTION_CONTAINER":
        p0 = swings[int(waves["0"]["swing_idx"])]
        p1 = swings[int(waves["1"]["swing_idx"])]
        p3 = swings[int(waves["3"]["swing_idx"])]
        p4 = swings[end_idx]
        correction = _evaluate_correction(
            swings,
            int(waves["3"]["swing_idx"]),
            end_idx,
            cfg,
            allow_triangle=True,
            source=source,
        )
        terminal_idx = int(correction.get("terminal_index", end_idx))
        p4 = swings[terminal_idx]
        correct_side = p4.kind == (-1 if bullish else 1)
        retrace = _safe_ratio(abs(p3.price - p4.price), abs(p3.price - p0.price))
        w3_terminal = "TERMINAL" in str(waves["3"]["subtype"])
        max_retrace = cfg.wave4_terminal_max_retrace if w3_terminal else cfg.wave4_max_retrace
        price_pass = _w4_minimum(cfg) <= retrace <= max_retrace
        p2 = swings[int(waves["2"]["swing_idx"])]
        flat_a_pass = _flat_a_minimum_pass(
            correction, swings, int(waves["3"]["swing_idx"]), abs(p3.price - p2.price), cfg
        )
        overlap = p4.price <= p1.price if bullish else p4.price >= p1.price
        overlap_invalid = overlap and not w3_terminal
        if correction["confirmed"] and correct_side and overlap_invalid:
            return _transition(
                status="INVALID",
                candidate_label="4?",
                pattern=str(correction["primary"]),
                subtype="NORMAL_W4_REJECTED",
                reason_code="W4_NORMAL_OVERLAP",
                note="Normal impulse Wave 4 entered Wave 1 territory; diagonal/terminal alternate required.",
                next_condition="Keep W4 container open or promote a valid terminal/diagonal alternate.",
                source_rule_id="V3-P26-W4-OVERLAP",
                alternate_pattern="Terminal/diagonal candidate",
                fib_anchor="Base-P3 retracement",
                fib_value=retrace,
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
            )
        if correction["confirmed"] and correct_side and flat_a_pass and price_pass:
            w2 = swings[int(waves["2"]["swing_idx"])]
            similarity = abs(float(waves["2"]["fib_value"]) - retrace)
            time_ratio = _duration_ratio(p3, p4, p1, w2)
            w2_duration = w2.position - p1.position
            w3_duration = p3.position - w2.position
            w4_duration = p4.position - p3.position
            time_gate = _matches_time_window(
                w4_duration,
                (w2_duration,),
                (0.50, 2.0, 3.0, 5.0),
                cfg.time_tolerance_bars,
            ) or _matches_time_window(
                w4_duration,
                (w2_duration + w3_duration,),
                (0.25, 0.50, 1.0),
                cfg.time_tolerance_bars,
            )
            if not time_gate:
                return _transition(
                    candidate_label="4?",
                    pattern=str(correction["primary"]),
                    subtype="W4_TIME_PENDING",
                    reason_code="W4_TIME_GATE_FAIL",
                    note=f"Wave 4 structure passes but duration {w4_duration} misses the V4 time windows.",
                    next_condition="W5 remains blocked until a permitted W4 time window passes.",
                    source_rule_id="V4-C08-W4-TIME",
                    alternate_pattern=str(correction["alternate"]),
                    fib_anchor="Base-P3 retracement",
                    fib_value=retrace,
                    time_value=time_ratio,
                    internal_pattern=str(correction["internal_pattern"]),
                    internal_count=int(correction["internal_count"]),
                )
            w4_subtype = (
                f"W4_{correction['subtype']}"
                if correction["primary"] == "Triangle"
                else "W4_NORMAL" if not w3_terminal else "W4_TERMINAL_CONTEXT"
            )
            record = _make_wave_record(
                swing_idx=terminal_idx,
                pattern=str(correction["primary"]),
                subtype=w4_subtype,
                reason_code="W4_CONFIRMED",
                source_rule_id="V4-C20-C21-W4",
                note=(
                    f"Wave 4 {correction['primary']} completed; Base-P3 retracement={retrace:.2%}; "
                    f"W2/W4 similarity difference={similarity:.2%}. "
                    + (
                        f"Triangle thrust={correction['thrust_min']:.4g}-{correction['thrust_max']:.4g}."
                        if correction["primary"] == "Triangle"
                        else ""
                    )
                ),
                fib_anchor="Base-P3 retracement",
                fib_value=retrace,
                time_value=time_ratio,
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
                alternate=str(correction["alternate"]),
                target_near=float(correction.get("thrust_target_near", np.nan)),
                target_far=float(correction.get("thrust_target_far", np.nan)),
                invalidation_price=float(
                    correction.get("invalidation_price", np.nan)
                ),
                confidence=(
                    90.0 if correction.get("target_cluster") else 80.0
                ),
                channel_type=str(correction.get("channel_type", "")),
                channel_target=float(correction.get("channel_target", np.nan)),
                target_cluster=str(correction.get("target_cluster", "")),
                support_evidence="CORRECTION_CHANNEL_CONFIRMED",
            )
            waves["4"] = record
            active["parent_state"] = "W5_FORMING"
            active["next_condition"] = "W4 is locked; evaluate normal/truncated/extended/ED Wave 5 candidates."
            return _transition(
                status="CONFIRMED",
                candidate_label="4",
                pattern=str(correction["primary"]),
                subtype=str(record["subtype"]),
                reason_code="W4_CONFIRMED",
                note=str(record["note"]),
                next_condition=active["next_condition"],
                source_rule_id="V4-C20-C21-W4",
                alternate_pattern=str(correction["alternate"]),
                fib_anchor="Base-P3 retracement",
                fib_value=retrace,
                time_value=time_ratio,
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
                confidence=float(record["confidence"]),
                channel_type=str(record["channel_type"]),
                channel_target=float(record["channel_target"]),
                target_cluster=str(record["target_cluster"]),
                support_evidence=str(record["support_evidence"]),
            )
        return _transition(
            candidate_label="4?" if correct_side else "",
            pattern=str(correction["primary"]),
            subtype="W4_CORRECTION_CONTAINER",
            reason_code=(
                "FLAT_A_LT_38_2"
                if correction["confirmed"] and not flat_a_pass
                else "W4_RETRACE_OUTSIDE_NORMAL"
                if correction["confirmed"]
                else str(correction["reason_code"])
            ),
            note=f"Wave 4 container remains open; retracement={retrace:.2%}; {correction['note']}",
            next_condition="Need a valid correction completion in the approved W4 range; W5 remains blocked.",
            source_rule_id="V3-P26-W4",
            alternate_pattern=str(correction["alternate"]),
            fib_anchor="Base-P3 retracement",
            fib_value=retrace,
            internal_pattern=str(correction["internal_pattern"]),
            internal_count=int(correction["internal_count"]),
        )

    if state == "W5_FORMING":
        p0 = swings[int(waves["0"]["swing_idx"])]
        p1 = swings[int(waves["1"]["swing_idx"])]
        p2 = swings[int(waves["2"]["swing_idx"])]
        p3 = swings[int(waves["3"]["swing_idx"])]
        p4 = swings[int(waves["4"]["swing_idx"])]
        p5 = swings[end_idx]
        internal_count = end_idx - int(waves["4"]["swing_idx"])
        correct_side = p5.kind == (1 if bullish else -1)
        ending_diagonal = _evaluate_diagonal(
            swings, int(waves["4"]["swing_idx"]), end_idx, "ending"
        )
        ending_confirmed = bool(ending_diagonal["confirmed"] and correct_side)
        internal_valid = bool(
            (internal_count in cfg.w1_internal_move_counts and correct_side)
            or ending_confirmed
        )
        ratio = _safe_ratio(abs(p5.price - p4.price), abs(p3.price - p4.price))
        w1_length = abs(p1.price - p0.price)
        w3_length = abs(p3.price - p2.price)
        w5_length = abs(p5.price - p4.price)
        w3_shortest = w3_length < w1_length and w3_length < w5_length
        divergence = (
            p5.price > p3.price and p5.macd_hist < p3.macd_hist
            if bullish
            else p5.price < p3.price and p5.macd_hist > p3.macd_hist
        )
        channel = _impulse_channel_evidence(
            p2, p3, p4, p5, bullish, divergence, cfg
        )
        divergence_pass = (
            bool(ending_diagonal.get("divergence", False))
            if ending_confirmed
            else cfg.wave5_divergence_mode != "Required" or divergence
        )
        normal = cfg.wave5_min_extension <= ratio <= cfg.wave5_max_extension
        double_extension = (
            float(waves["1"]["internal_count"]) > 5
            and float(waves["3"]["internal_count"]) > 5
        )
        truncated = double_extension and ratio <= 0.812
        price_subtype_pass = normal or truncated or ending_confirmed
        if internal_valid and not w3_shortest and divergence_pass and price_subtype_pass:
            w1_duration = p1.position - p0.position
            w3_duration = p3.position - p2.position
            w4_duration = p4.position - p3.position
            w5_duration = p5.position - p4.position
            time_targets = (
                float(w1_duration),
                float(w4_duration),
                (w1_duration + w3_duration) / 4.0,
                (w1_duration + w3_duration) / 2.0,
                float(w1_duration + w3_duration),
                (w3_duration + w4_duration) / 2.0,
            )
            if not _matches_absolute_time_targets(
                w5_duration, time_targets, cfg.time_tolerance_bars
            ):
                return _transition(
                    candidate_label="5?",
                    pattern="Ending Diagonal" if ending_confirmed else "Motive",
                    subtype="W5_TIME_PENDING",
                    reason_code="W5_TIME_GATE_FAIL",
                    note=f"Wave 5 structure passes but duration {w5_duration} misses the V4 time windows.",
                    next_condition="Wait for a permitted W5 time window; the completed W4 remains locked.",
                    source_rule_id="V4-C09-W5-TIME",
                    fib_anchor="P3-P4 projection",
                    fib_value=ratio,
                    macd_state="W3/W5 DIVERGENCE PASS" if divergence else "W3/W5 DIVERGENCE ABSENT",
                    internal_pattern=(
                        str(ending_diagonal["internal_pattern"])
                        if ending_confirmed
                        else "5/9/13/17/21-move impulse"
                    ),
                    internal_count=internal_count,
                    confidence=float(channel["confidence"]),
                    channel_type=str(channel["channel_type"]),
                    channel_target=float(channel["channel_target"]),
                    target_cluster=str(channel["target_cluster"]),
                    fbd_candidate=str(channel["fbd_candidate"]),
                    support_evidence=str(channel["support_evidence"]),
                )
            subtype = (
                f"W5_{ending_diagonal['subtype']}"
                if ending_confirmed
                else "W5_TRUNCATED"
                if truncated
                else "W5_NORMAL"
            )
            pattern = "Ending Diagonal" if ending_confirmed else "Motive"
            internal_pattern = (
                str(ending_diagonal["internal_pattern"])
                if ending_confirmed
                else "5/9/13/17/21-move impulse"
            )
            macd_state = "W3/W5 DIVERGENCE PASS" if divergence else "W3/W5 DIVERGENCE ABSENT"
            time_ratio = _duration_ratio(p4, p5, p0, p1)
            record = _make_wave_record(
                swing_idx=end_idx,
                pattern=pattern,
                subtype=subtype,
                reason_code="W5_CONFIRMED",
                source_rule_id="V3-P26-27-W5",
                note=f"{subtype} confirmed; 3-4 projection={ratio:.2%}; W3 shortest=false.",
                fib_anchor="P3-P4 projection",
                fib_value=ratio,
                time_value=time_ratio,
                macd_state=macd_state,
                internal_pattern=internal_pattern,
                internal_count=internal_count,
                confidence=min(100.0, float(channel["confidence"]) + 10.0),
                channel_type=str(channel["channel_type"]),
                channel_target=float(channel["channel_target"]),
                target_cluster=str(channel["target_cluster"]),
                fbd_candidate=str(channel["fbd_candidate"]),
                support_evidence=str(channel["support_evidence"]),
            )
            waves["5"] = record
            active["parent_state"] = "LARGER_CORRECTION_CONTAINER"
            active["next_condition"] = "Five-wave impulse locked; classify the larger correction in parallel."
            return _transition(
                status="CONFIRMED",
                candidate_label="5",
                pattern=pattern,
                subtype=subtype,
                reason_code="W5_CONFIRMED",
                note=str(record["note"]),
                next_condition=active["next_condition"],
                source_rule_id="V3-P26-27-W5",
                fib_anchor="P3-P4 projection",
                fib_value=ratio,
                time_value=time_ratio,
                macd_state=macd_state,
                internal_pattern=internal_pattern,
                internal_count=internal_count,
                confidence=float(record["confidence"]),
                channel_type=str(record["channel_type"]),
                channel_target=float(record["channel_target"]),
                target_cluster=str(record["target_cluster"]),
                fbd_candidate=str(record["fbd_candidate"]),
                support_evidence=str(record["support_evidence"]),
            )
        extension_conflict = bool(
            np.isfinite(ratio) and ratio > cfg.wave5_max_extension
        )
        reason = (
            "W5_W3_SHORTEST"
            if w3_shortest
            else "W5_INTERNAL_FAIL"
            if not internal_valid
            else "W5_EXTENSION_REQUIRES_INSTRUMENT_RULE"
            if extension_conflict
            else "W5_PRICE_SUBTYPE_PENDING"
        )
        return _transition(
            status="INVALID" if w3_shortest else "FORMING",
            candidate_label="5?" if correct_side else "",
            pattern="Motive",
            subtype=(
                "W5_EXTENSION_SOURCE_CONFLICT"
                if extension_conflict
                else "W5_CANDIDATE"
            ),
            reason_code=reason,
            note=f"Wave 5 forming: 3-4 projection={ratio:.2%}, internal moves={internal_count}.",
            next_condition="Need a valid normal/truncated/extended/ED subtype and deferred W3-shortest check.",
            source_rule_id="V3-P26-27-W5",
            fib_anchor="P3-P4 projection",
            fib_value=ratio,
            macd_state="W3/W5 DIVERGENCE PASS" if divergence else "W3/W5 DIVERGENCE ABSENT",
            internal_pattern="Impulse candidate",
            internal_count=internal_count,
            confidence=float(channel["confidence"]),
            channel_type=str(channel["channel_type"]),
            channel_target=float(channel["channel_target"]),
            target_cluster=str(channel["target_cluster"]),
            fbd_candidate=str(channel["fbd_candidate"]),
            support_evidence=str(channel["support_evidence"]),
        )

    if state == "LARGER_CORRECTION_CONTAINER":
        start_idx = int(waves["5"]["swing_idx"])
        correction = _evaluate_correction(
            swings,
            start_idx,
            end_idx,
            cfg,
            allow_triangle=True,
            source=source,
        )
        terminal_idx = int(correction.get("terminal_index", end_idx))
        terminal = swings[terminal_idx]
        correct_side = terminal.kind == (-1 if bullish else 1)
        p4 = swings[int(waves["4"]["swing_idx"])]
        p5 = swings[int(waves["5"]["swing_idx"])]
        flat_a_pass = _flat_a_minimum_pass(
            correction, swings, start_idx, abs(p5.price - p4.price), cfg
        )
        if correction["confirmed"] and correct_side and flat_a_pass:
            endpoint_indices = correction["endpoint_indices"]
            terminal_labels = correction["labels"]
            fib_values = correction.get("fib_values", {})
            for label, endpoint_idx in zip(terminal_labels, endpoint_indices):
                endpoint = swings[int(endpoint_idx)]
                waves[label] = _make_wave_record(
                    swing_idx=int(endpoint_idx),
                    pattern=str(correction["primary"]),
                    subtype=f"{correction['primary'].upper().replace('-', '_')}_{label}",
                    reason_code=f"{label}_CONFIRMED",
                    source_rule_id="V4-C10-C16-LARGER-CORRECTION",
                    note=(
                        f"Larger {correction['primary']} Wave {label} confirmed at "
                        f"{endpoint.confirmed_index}."
                    ),
                    fib_anchor="Wave 5 correction origin",
                    fib_value=float(fib_values.get(label, np.nan)),
                    internal_pattern=str(correction["internal_pattern"]),
                    internal_count=int(correction["leg_counts"][label]),
                    alternate=str(correction["alternate"]),
                    target_near=(
                        float(correction.get("thrust_target_near", np.nan))
                        if label == terminal_labels[-1]
                        else np.nan
                    ),
                    target_far=(
                        float(correction.get("thrust_target_far", np.nan))
                        if label == terminal_labels[-1]
                        else np.nan
                    ),
                    invalidation_price=(
                        float(correction.get("invalidation_price", np.nan))
                        if label == terminal_labels[-1]
                        else np.nan
                    ),
                )
            active["parent_state"] = "CORRECTION_CONFIRMED"
            terminal_sequence = "-".join(terminal_labels)
            active["next_condition"] = f"The 1-2-3-4-5 then {terminal_sequence} cycle is complete; wait for the next qualified Point 0."
            return _transition(
                status="CONFIRMED",
                candidate_label=str(terminal_labels[-1]),
                pattern=str(correction["primary"]),
                subtype="LARGER_CORRECTION_COMPLETE",
                reason_code="CORRECTION_COMPLETE",
                note=(
                    f"Larger {correction['primary']} completed as "
                    f"{correction['internal_pattern']}; {terminal_sequence} labels locked on actual pivots."
                ),
                next_condition=active["next_condition"],
                source_rule_id="V4-C10-C16-LARGER-CORRECTION",
                alternate_pattern=str(correction["alternate"]),
                fib_anchor="Wave 5 correction origin",
                fib_value=float(correction.get("terminal_fib_value", np.nan)),
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
            )

        candidate_label = str(
            correction.get(
                "developing_label",
                _larger_correction_candidate_label(end_idx - start_idx, cfg),
            )
        )
        return _transition(
            candidate_label=candidate_label,
            pattern=str(correction["primary"]),
            subtype="LARGER_CORRECTION_CONTAINER",
            reason_code=(
                "FLAT_A_LT_38_2"
                if correction["confirmed"] and not flat_a_pass
                else str(correction["reason_code"])
            ),
            note=(
                "The motive 1-2-3-4-5 count is locked. The larger correction "
                f"remains FORMING: {correction['note']}"
            ),
            next_condition="Need an actual completed terminal C (or later Y/Z/E family) before confirmation.",
            source_rule_id="V4-C10-C21-LARGER-CORRECTION",
            alternate_pattern=str(correction["alternate"]),
            internal_pattern=str(correction["internal_pattern"]),
            internal_count=int(correction["internal_count"]),
        )

    return _transition(
        status="CONFIRMED",
        pattern="Completed market cycle",
        subtype="MOTIVE_PLUS_CORRECTION",
        reason_code="CYCLE_COMPLETE",
        note="Confirmed 1-2-3-4-5 motive sequence followed by confirmed A-B-C correction.",
        next_condition="Wait for the next independently qualified Point 0 candidate.",
        source_rule_id="V4-MARKET-CYCLE",
    )


def _evaluate_correction(
    swings: list[_Swing],
    start_idx: int,
    end_idx: int,
    cfg: ElliottWaveConfig,
    *,
    allow_triangle: bool = False,
    source: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Run permitted correction families in parallel and rank hard-valid results."""

    simple = _evaluate_simple_correction(swings, start_idx, end_idx, cfg)
    double = _evaluate_double_correction(
        swings,
        start_idx,
        end_idx,
        cfg,
        allow_triangle=allow_triangle,
        source=source,
    )
    triple = (
        _evaluate_triple_correction(swings, start_idx, end_idx, cfg)
        if allow_triangle
        else None
    )
    candidates = [candidate for candidate in (triple, double) if candidate is not None]
    if allow_triangle:
        triangle = _evaluate_triangle_correction(
            swings, start_idx, end_idx, source=source
        )
        candidates.append(triangle)
    candidates.append(simple)

    confirmed = [candidate for candidate in candidates if candidate["confirmed"]]
    if confirmed:
        confirmed.sort(key=_correction_rank_key)
        primary = confirmed[0]
        alternates = [
            str(candidate["primary"])
            for candidate in confirmed[1:]
            if candidate["primary"] != primary["primary"]
        ]
        if alternates:
            primary["alternate"] = " | ".join(
                list(dict.fromkeys(alternates))[:2]
            )
        return _with_correction_defaults(primary, end_idx)

    progressed = [
        candidate
        for candidate in candidates
        if int(candidate.get("progress_score", 0)) > 0
    ]
    forming = max(
        progressed,
        key=lambda candidate: int(candidate.get("progress_score", 0)),
    ) if progressed else simple
    alternates = [
        str(candidate["primary"])
        for candidate in candidates
        if candidate is not forming and int(candidate.get("progress_score", 0)) > 0
    ]
    if alternates:
        forming["alternate"] = " | ".join(list(dict.fromkeys(alternates))[:2])
    return _with_correction_defaults(forming, end_idx)


def _with_correction_defaults(
    candidate: dict[str, object], end_idx: int
) -> dict[str, object]:
    """Normalize the shared correction result contract for every family."""

    candidate.setdefault("terminal_index", end_idx)
    candidate.setdefault("confirmation_index", end_idx)
    candidate.setdefault("terminal_fib_value", candidate.get("c_vs_a", np.nan))
    candidate.setdefault("fib_values", {})
    candidate.setdefault("developing_label", "C?")
    candidate.setdefault("progress_score", 0)
    candidate.setdefault("thrust_target_near", np.nan)
    candidate.setdefault("thrust_target_far", np.nan)
    candidate.setdefault("invalidation_price", np.nan)
    candidate.setdefault("mandatory_gate_count", 0)
    candidate.setdefault("subdivision_score", 0)
    candidate.setdefault("fib_error", float("inf"))
    candidate.setdefault("time_error", float("inf"))
    candidate.setdefault("parent_score", 0)
    candidate.setdefault("channel_type", "")
    candidate.setdefault("channel_target", np.nan)
    candidate.setdefault("target_cluster", "")
    candidate.setdefault("fbd_candidate", "")
    candidate.setdefault("support_evidence", "")
    return candidate


def _correction_rank_key(candidate: dict[str, object]) -> tuple[float, ...]:
    """Return the deterministic V4 Section 24 correction ranking key."""

    return (
        0.0 if bool(candidate.get("confirmed")) else 1.0,
        -float(candidate.get("mandatory_gate_count", 0)),
        -float(candidate.get("subdivision_score", 0)),
        float(candidate.get("fib_error", float("inf"))),
        float(candidate.get("time_error", float("inf"))),
        -float(candidate.get("parent_score", 0)),
        float(candidate.get("confirmation_index", float("inf"))),
    )


def _component_total_counts(cfg: ElliottWaveConfig) -> tuple[int, ...]:
    correction_counts = (3, 7, 11)
    totals = {
        a + b + c
        for a in (*cfg.w1_internal_move_counts, *correction_counts)
        for b in correction_counts
        for c in cfg.w1_internal_move_counts
    }
    # V4 acceptance combinations use canonical Flat (11), Zig-Zag (13) and
    # five-leg/extended component (15) containers. Bounding the parent search
    # to these totals keeps Pine/Python parity deterministic and avoids an
    # exponential candidate explosion. V4 Q1 locks W to a simple Zig-Zag/Flat
    # component and Y to Zig-Zag/Flat/Triangle at this degree; lower-degree
    # subdivisions belong to the degree router and are not guessed recursively.
    return tuple(total for total in (11, 13, 15) if total in totals)


def _evaluate_component(
    swings: list[_Swing],
    start_idx: int,
    end_idx: int,
    cfg: ElliottWaveConfig,
    *,
    allow_triangle: bool = False,
) -> dict[str, object]:
    simple = _evaluate_simple_correction(swings, start_idx, end_idx, cfg)
    if allow_triangle:
        triangle = _evaluate_triangle_correction(
            swings, start_idx, end_idx, require_break=False
        )
        if triangle["confirmed"]:
            return triangle
    return simple


def _connector_classification(
    swings: list[_Swing], start_idx: int, end_idx: int, reference_length: float
) -> tuple[str, float]:
    length = abs(swings[end_idx].price - swings[start_idx].price)
    ratio = _safe_ratio(length, reference_length)
    if np.isfinite(ratio) and 0.142 <= ratio <= 0.50:
        return "SMALL", ratio
    if np.isfinite(ratio) and 0.618 <= ratio <= 1.11:
        return "LARGE", ratio
    return "", ratio


def _double_post_y_confirmation(
    swings: list[_Swing],
    start_idx: int,
    x_idx: int,
    y_idx: int,
    end_idx: int,
    source: pd.DataFrame | None = None,
) -> tuple[bool, int, str]:
    """Apply V3.3 C19 using closed, confirmed swing observations."""

    if end_idx <= y_idx:
        return False, y_idx, ""
    origin = swings[start_idx]
    x = swings[x_idx]
    y = swings[y_idx]
    y_duration = max(1, y.position - x.position)
    deadline = y.position + y_duration
    wxy_range = abs(y.price - origin.price)
    downward = y.price < origin.price
    line_denominator = max(1, x.position - origin.position)
    line_slope = (x.price - origin.price) / line_denominator

    observations: list[tuple[int, float, int]] = []
    if source is not None and "close" in source:
        # V3.3 C19 starts with the first closed candle after terminal Y. The
        # engine may recognize the Y pivot later, but it must not discard
        # already-closed post-Y evidence when it evaluates that pivot.
        first_position = y.position + 1
        last_position = min(
            deadline,
            swings[end_idx].confirmed_position,
            len(source) - 1,
        )
        observations.extend(
            (position, float(source["close"].iloc[position]), end_idx)
            for position in range(first_position, last_position + 1)
        )
    else:
        observations.extend(
            (swings[index].position, swings[index].price, index)
            for index in range(y_idx + 1, end_idx + 1)
            if swings[index].position <= deadline
        )

    for observed_position, observed_price, observed_index in observations:
        retrace = _safe_ratio(
            observed_price - y.price if downward else y.price - observed_price,
            wxy_range,
        )
        line_value = origin.price + line_slope * (observed_position - origin.position)
        trendline_break = observed_price > line_value if downward else observed_price < line_value
        if trendline_break:
            return True, observed_index, "0-X_CLOSED_BREAK"
        if np.isfinite(retrace) and retrace >= 0.382:
            return True, observed_index, "WXY_38_2_RETRACE"
    return False, y_idx, ""


def _evaluate_double_correction(
    swings: list[_Swing],
    start_idx: int,
    end_idx: int,
    cfg: ElliottWaveConfig,
    *,
    allow_triangle: bool,
    source: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Evaluate V4 Double Correction W-X-Y and its locked post-Y gate."""

    component_counts = _component_total_counts(cfg)
    connector_counts = (1, 3, 7, 11)
    cache: dict[tuple[int, int, bool], dict[str, object]] = {}

    def component(left: int, right: int, triangle: bool = False) -> dict[str, object]:
        key = (left, right, triangle)
        if key not in cache:
            cache[key] = _evaluate_component(
                swings, left, right, cfg, allow_triangle=triangle
            )
        return cache[key]

    best_forming: dict[str, object] | None = None
    for w_count in component_counts:
        w_idx = start_idx + w_count
        if w_idx >= end_idx:
            continue
        w = component(start_idx, w_idx)
        if not w["confirmed"]:
            continue
        w_length = abs(swings[w_idx].price - swings[start_idx].price)
        w_duration = max(1, swings[w_idx].position - swings[start_idx].position)
        for x_count in connector_counts:
            x_idx = w_idx + x_count
            if x_idx >= end_idx:
                continue
            x_class, x_ratio = _connector_classification(
                swings, w_idx, x_idx, w_length
            )
            x_duration = max(1, swings[x_idx].position - swings[w_idx].position)
            x_time_pass = x_duration < w_duration and _matches_absolute_time_targets(
                x_duration,
                (0.25 * w_duration, w_duration / 3.0, 0.50 * w_duration),
                cfg.time_tolerance_bars,
            )
            if not x_class or not x_time_pass:
                continue
            for y_count in component_counts:
                y_idx = x_idx + y_count
                if y_idx > end_idx:
                    continue
                y = component(x_idx, y_idx, allow_triangle)
                if not y["confirmed"]:
                    continue
                y_duration = max(1, swings[y_idx].position - swings[x_idx].position)
                y_time_pass = _matches_absolute_time_targets(
                    y_duration,
                    (
                        w_duration,
                        w_duration + x_duration,
                        0.50 * (w_duration + x_duration),
                    ),
                    cfg.time_tolerance_bars,
                )
                y_projection = _safe_ratio(
                    abs(swings[y_idx].price - swings[x_idx].price), w_length
                )
                y_max = 1.0 if w["primary"] == "Zig-Zag" and y["primary"] == "Triangle" else 2.618 if w["primary"] == "Zig-Zag" and y["primary"] == "Zig-Zag" else 1.618
                if not (
                    y_time_pass
                    and np.isfinite(y_projection)
                    and 0.618 <= y_projection <= y_max
                ):
                    continue
                confirmed, confirmation_idx, confirmation_mode = _double_post_y_confirmation(
                    swings, start_idx, x_idx, y_idx, end_idx, source
                )
                result = {
                    "confirmed": confirmed,
                    "primary": "W-X-Y",
                    "alternate": "",
                    "subtype": f"DOUBLE_{w['primary'].upper().replace('-', '_')}_{y['primary'].upper().replace('-', '_')}",
                    "b_ratio": x_ratio,
                    "c_vs_a": y_projection,
                    "c_vs_b": np.nan,
                    "labels": ("W", "X", "Y"),
                    "leg_counts": {"W": w_count, "X": x_count, "Y": y_count},
                    "endpoint_indices": (w_idx, x_idx, y_idx),
                    "terminal_index": y_idx,
                    "confirmation_index": confirmation_idx,
                    "terminal_fib_value": y_projection,
                    "fib_values": {"X": x_ratio, "Y": y_projection},
                    "internal_pattern": f"{w['internal_pattern']} | X{x_count} | {y['internal_pattern']}",
                    "internal_count": y_idx - start_idx,
                    "reason_code": "DOUBLE_CONFIRMED" if confirmed else "DOUBLE_CONFIRMATION_PENDING",
                    "developing_label": "Y?",
                    "progress_score": 4 if confirmed else 3,
                    "mandatory_gate_count": 8,
                    "subdivision_score": 3,
                    "fib_error": _nearest_error(
                        x_ratio, (0.142, 0.25, 1.0 / 3.0, 0.50, 0.618, 1.0, 1.11)
                    )
                    + _nearest_error(y_projection, (0.618, 1.0, 1.618, 2.618)),
                    "time_error": _nearest_error(
                        float(x_duration),
                        (0.25 * w_duration, w_duration / 3.0, 0.50 * w_duration),
                    )
                    + _nearest_error(
                        float(y_duration),
                        (
                            float(w_duration),
                            float(w_duration + x_duration),
                            0.50 * (w_duration + x_duration),
                        ),
                    ),
                    "note": (
                        f"W-X-Y {w['primary']} + {y['primary']}; X={x_ratio:.2%} ({x_class}), "
                        f"Y={y_projection:.2%}; X/Y time gates pass. "
                        + (
                            f"Post-Y confirmation={confirmation_mode}."
                            if confirmed
                            else "Await first closed 0-X break or >=38.2% WXY retracement within Y duration."
                        )
                    ),
                }
                if confirmed:
                    return result
                best_forming = result

    if best_forming is not None:
        return best_forming
    return {
        "confirmed": False,
        "primary": "W-X-Y",
        "alternate": "",
        "subtype": "DOUBLE_FORMING",
        "b_ratio": np.nan,
        "c_vs_a": np.nan,
        "c_vs_b": np.nan,
        "labels": ("W", "X", "Y"),
        "leg_counts": {},
        "endpoint_indices": (),
        "internal_pattern": "W + X + Y component containers",
        "internal_count": max(0, end_idx - start_idx),
        "reason_code": "DOUBLE_COMPONENT_PENDING",
        "developing_label": "W?" if end_idx - start_idx < 11 else "X?",
        "progress_score": 0,
        "note": "W, X or Y structure/Fib/time gates are incomplete.",
    }


def _evaluate_triple_correction(
    swings: list[_Swing], start_idx: int, end_idx: int, cfg: ElliottWaveConfig
) -> dict[str, object]:
    """Evaluate V4 Triple Correction W-X-Y-XX-Z with distinct connectors."""

    component_counts = _component_total_counts(cfg)
    connector_counts = (1, 3, 7, 11)
    cache: dict[tuple[int, int, bool], dict[str, object]] = {}

    def component(left: int, right: int, triangle: bool = False) -> dict[str, object]:
        key = (left, right, triangle)
        if key not in cache:
            cache[key] = _evaluate_component(
                swings, left, right, cfg, allow_triangle=triangle
            )
        return cache[key]

    for w_count in component_counts:
        w_idx = start_idx + w_count
        if w_idx >= end_idx:
            continue
        w = component(start_idx, w_idx)
        if not w["confirmed"]:
            continue
        w_length = abs(swings[w_idx].price - swings[start_idx].price)
        w_duration = max(1, swings[w_idx].position - swings[start_idx].position)
        for x_count in connector_counts:
            x_idx = w_idx + x_count
            if x_idx >= end_idx:
                continue
            x_class, x_ratio = _connector_classification(swings, w_idx, x_idx, w_length)
            x_duration = max(1, swings[x_idx].position - swings[w_idx].position)
            if not x_class or not (
                x_duration < w_duration
                and _matches_absolute_time_targets(
                    x_duration,
                    (0.25 * w_duration, w_duration / 3.0, 0.50 * w_duration),
                    cfg.time_tolerance_bars,
                )
            ):
                continue
            for y_count in component_counts:
                y_idx = x_idx + y_count
                if y_idx >= end_idx:
                    continue
                y = component(x_idx, y_idx, True)
                if not y["confirmed"]:
                    continue
                y_length = abs(swings[y_idx].price - swings[x_idx].price)
                y_projection = _safe_ratio(y_length, w_length)
                y_duration = max(1, swings[y_idx].position - swings[x_idx].position)
                if not (
                    np.isfinite(y_projection)
                    and 0.618 <= y_projection <= 1.618
                    and _matches_absolute_time_targets(
                        y_duration,
                        (
                            w_duration,
                            w_duration + x_duration,
                            0.50 * (w_duration + x_duration),
                        ),
                        cfg.time_tolerance_bars,
                    )
                ):
                    continue
                for xx_count in connector_counts:
                    xx_idx = y_idx + xx_count
                    z_count = end_idx - xx_idx
                    if xx_idx >= end_idx or z_count not in component_counts:
                        continue
                    xx_length = abs(swings[xx_idx].price - swings[y_idx].price)
                    xx_ratio = _safe_ratio(xx_length, y_length)
                    xx_duration = max(1, swings[xx_idx].position - swings[y_idx].position)
                    x_boundary_pass = (
                        swings[xx_idx].price <= swings[x_idx].price
                        if swings[x_idx].kind == 1
                        else swings[xx_idx].price >= swings[x_idx].price
                    )
                    if not (
                        np.isfinite(xx_ratio)
                        and 0.50 <= xx_ratio <= 0.618
                        and x_boundary_pass
                        and abs(xx_duration - x_duration) <= cfg.time_tolerance_bars
                        and xx_duration < y_duration
                    ):
                        continue
                    z = component(xx_idx, end_idx, True)
                    if not z["confirmed"]:
                        continue
                    z_length = abs(swings[end_idx].price - swings[xx_idx].price)
                    z_projection = _safe_ratio(z_length, y_length)
                    z_duration = max(1, swings[end_idx].position - swings[xx_idx].position)
                    if not (
                        np.isfinite(z_projection)
                        and 0.618 <= z_projection <= 1.618
                        and _matches_absolute_time_targets(
                            z_duration,
                            (
                                y_duration,
                                y_duration + xx_duration,
                                0.50 * (y_duration + xx_duration),
                            ),
                            cfg.time_tolerance_bars,
                        )
                    ):
                        continue
                    return {
                        "confirmed": True,
                        "primary": "W-X-Y-XX-Z",
                        "alternate": "",
                        "subtype": "TRIPLE_COMPLETE",
                        "b_ratio": x_ratio,
                        "c_vs_a": y_projection,
                        "c_vs_b": z_projection,
                        "labels": ("W", "X", "Y", "XX", "Z"),
                        "leg_counts": {
                            "W": w_count,
                            "X": x_count,
                            "Y": y_count,
                            "XX": xx_count,
                            "Z": z_count,
                        },
                        "endpoint_indices": (w_idx, x_idx, y_idx, xx_idx, end_idx),
                        "terminal_index": end_idx,
                        "confirmation_index": end_idx,
                        "terminal_fib_value": z_projection,
                        "fib_values": {
                            "X": x_ratio,
                            "Y": y_projection,
                            "XX": xx_ratio,
                            "Z": z_projection,
                        },
                        "internal_pattern": (
                            f"{w['internal_pattern']} | X{x_count} | {y['internal_pattern']} | "
                            f"XX{xx_count} | {z['internal_pattern']}"
                        ),
                        "internal_count": end_idx - start_idx,
                        "reason_code": "TRIPLE_CONFIRMED",
                        "developing_label": "Z",
                        "progress_score": 5,
                        "mandatory_gate_count": 12,
                        "subdivision_score": 5,
                        "fib_error": _nearest_error(
                            x_ratio,
                            (0.142, 0.25, 1.0 / 3.0, 0.50, 0.618, 1.0, 1.11),
                        )
                        + _nearest_error(y_projection, (0.618, 1.0, 1.618, 2.618))
                        + _nearest_error(xx_ratio, (0.50, 0.618))
                        + _nearest_error(z_projection, (0.618, 1.0, 1.618)),
                        "time_error": _nearest_error(
                            float(xx_duration), (float(x_duration),)
                        )
                        + _nearest_error(
                            float(z_duration),
                            (
                                float(y_duration),
                                float(y_duration + xx_duration),
                                0.50 * (y_duration + xx_duration),
                            ),
                        ),
                        "note": (
                            f"W-X-Y-XX-Z complete; X={x_ratio:.2%} ({x_class}), "
                            f"Y={y_projection:.2%}, XX={xx_ratio:.2%}, Z={z_projection:.2%}; "
                            "all locked Fib/time and X-boundary gates pass."
                        ),
                    }

    return {
        "confirmed": False,
        "primary": "W-X-Y-XX-Z",
        "alternate": "",
        "subtype": "TRIPLE_FORMING",
        "b_ratio": np.nan,
        "c_vs_a": np.nan,
        "c_vs_b": np.nan,
        "labels": ("W", "X", "Y", "XX", "Z"),
        "leg_counts": {},
        "endpoint_indices": (),
        "internal_pattern": "W + X + Y + XX + Z component containers",
        "internal_count": max(0, end_idx - start_idx),
        "reason_code": "TRIPLE_COMPONENT_PENDING",
        "developing_label": "Z?",
        "progress_score": 0,
        "note": "Triple component, connector, Fib, boundary or time gates are incomplete.",
    }


def _evaluate_triangle_correction(
    swings: list[_Swing],
    start_idx: int,
    end_idx: int,
    *,
    source: pd.DataFrame | None = None,
    require_break: bool = True,
) -> dict[str, object]:
    """Evaluate six V4 triangle families and the closed B-D break gate."""

    correction_counts = (3, 7, 11)
    for a_count in correction_counts:
        for b_count in correction_counts:
            for c_count in correction_counts:
                for d_count in correction_counts:
                    for e_count in correction_counts:
                        counts = (a_count, b_count, c_count, d_count, e_count)
                        terminal_idx = start_idx + sum(counts)
                        if terminal_idx > end_idx:
                            continue
                        endpoints: list[int] = []
                        cursor = start_idx
                        for count in counts:
                            cursor += count
                            endpoints.append(cursor)
                        points = [swings[start_idx], *(swings[index] for index in endpoints)]
                        lengths = tuple(
                            abs(points[index + 1].price - points[index].price)
                            for index in range(5)
                        )
                        if min(lengths) <= 0:
                            continue
                        retrace_passes = sum(
                            lengths[index] / lengths[index - 1] >= 0.50
                            for index in range(1, 5)
                        )
                        if retrace_passes < 3:
                            continue
                        a, b, c, d, e = lengths
                        pa, pb, pc, pd, pe = points[1:]
                        ac_slope = (pc.price - pa.price) / max(1, pc.position - pa.position)
                        bd_slope = (pd.price - pb.price) / max(1, pd.position - pb.position)
                        opposite_boundaries = ac_slope * bd_slope < 0
                        same_direction_boundaries = ac_slope * bd_slope > 0

                        subtype = ""
                        family = ""
                        if a > b > c > d > e and opposite_boundaries:
                            subtype, family = "HORIZONTAL_CONTRACTING", "contracting"
                        elif b > a and b > c > d > e and b <= 2.618 * a and opposite_boundaries:
                            subtype, family = "IRREGULAR_CONTRACTING", "contracting"
                        elif b > a and b > c and d > c and e < d and b == max(lengths) and same_direction_boundaries:
                            subtype, family = "RUNNING_CONTRACTING", "contracting"
                        elif a == min(lengths) and a < b < c < d < e and opposite_boundaries:
                            subtype, family = "HORIZONTAL_EXPANDING", "expanding"
                        elif b == min(lengths) and c > b and d > c and e > d and e == max(lengths) and opposite_boundaries:
                            subtype, family = "IRREGULAR_EXPANDING", "expanding"
                        elif b > a and c < b and d > c and e > d and e == max(lengths) and same_direction_boundaries:
                            subtype, family = "RUNNING_EXPANDING", "expanding"
                        if not subtype:
                            continue

                        ac_touches = _triangle_line_touch_count(
                            swings, start_idx, terminal_idx, endpoints[0], endpoints[2]
                        )
                        bd_touches = _triangle_line_touch_count(
                            swings, start_idx, terminal_idx, endpoints[1], endpoints[3]
                        )
                        touch_pass = ac_touches <= 5 and bd_touches <= 5
                        apex_position = _line_intersection_position(pa, pc, pb, pd)
                        longest_duration = max(
                            points[index + 1].position - points[index].position
                            for index in range(5)
                        )
                        apex_pass = bool(
                            subtype != "HORIZONTAL_CONTRACTING"
                            or (
                                np.isfinite(apex_position)
                                and pe.position <= apex_position
                                <= pe.position + 0.618 * longest_duration
                            )
                        )
                        if not touch_pass or not apex_pass:
                            continue

                        break_confirmed, confirmation_idx = _triangle_post_e_confirmation(
                            swings,
                            endpoints[1],
                            endpoints[3],
                            endpoints[4],
                            end_idx,
                            source,
                        )
                        confirmed = not require_break or break_confirmed

                        thrust_base = max(lengths) if family == "contracting" else e
                        thrust_min = 0.75 * thrust_base if family == "contracting" else 0.618 * thrust_base
                        thrust_max = 1.25 * thrust_base if family == "contracting" else thrust_base
                        thrust_sign = 1.0 if swings[start_idx].kind == 1 else -1.0
                        thrust_target_near = pe.price + thrust_sign * thrust_min
                        thrust_target_far = pe.price + thrust_sign * thrust_max
                        return {
                            "confirmed": confirmed,
                            "primary": "Triangle",
                            "alternate": "",
                            "subtype": subtype,
                            "b_ratio": _safe_ratio(b, a),
                            "c_vs_a": _safe_ratio(c, a),
                            "c_vs_b": _safe_ratio(c, b),
                            "labels": ("A", "B", "C", "D", "E"),
                            "leg_counts": dict(zip(("A", "B", "C", "D", "E"), counts)),
                            "endpoint_indices": tuple(endpoints),
                            "terminal_index": terminal_idx,
                            "confirmation_index": (
                                confirmation_idx if confirmed else terminal_idx
                            ),
                            "internal_pattern": "-".join(str(count) for count in counts),
                            "internal_count": sum(counts),
                            "reason_code": (
                                "TRIANGLE_CONFIRMED"
                                if confirmed
                                else "TRIANGLE_BD_BREAK_PENDING"
                            ),
                            "progress_score": 5 if confirmed else 4,
                            "mandatory_gate_count": 7,
                            "subdivision_score": 5,
                            "fib_error": sum(
                                _nearest_error(
                                    lengths[index] / lengths[index - 1],
                                    (0.50, 0.618, 0.812, 1.0),
                                )
                                for index in range(1, 5)
                            ),
                            "time_error": 0.0,
                            "apex_position": apex_position,
                            "touch_counts": {"A-C": ac_touches, "B-D": bd_touches},
                            "thrust_min": thrust_min,
                            "thrust_max": thrust_max,
                            "thrust_target_near": thrust_target_near,
                            "thrust_target_far": thrust_target_far,
                            "invalidation_price": pe.price,
                            "note": (
                                f"{subtype} passes five corrective legs, size order, "
                                f"three >=50% retracements, apex/touch geometry; "
                                f"thrust={thrust_min:.4g}-{thrust_max:.4g}. "
                                + (
                                    "Closed B-D break=PASS."
                                    if confirmed
                                    else "Await a closed B-D trendline break after E."
                                )
                            ),
                        }

    return {
        "confirmed": False,
        "primary": "Triangle",
        "alternate": "",
        "subtype": "TRIANGLE_FORMING",
        "b_ratio": np.nan,
        "c_vs_a": np.nan,
        "c_vs_b": np.nan,
        "labels": ("A", "B", "C", "D", "E"),
        "leg_counts": {},
        "endpoint_indices": (),
        "internal_pattern": "3/7/11 corrective legs",
        "internal_count": max(0, end_idx - start_idx),
        "reason_code": "TRIANGLE_GEOMETRY_PENDING",
        "progress_score": 0,
        "thrust_min": np.nan,
        "thrust_max": np.nan,
        "thrust_target_near": np.nan,
        "thrust_target_far": np.nan,
        "invalidation_price": np.nan,
        "note": "Five-leg size sequence or boundary geometry is incomplete.",
    }


def _line_intersection_position(
    a1: _Swing, a2: _Swing, b1: _Swing, b2: _Swing
) -> float:
    a_slope = (a2.price - a1.price) / max(1, a2.position - a1.position)
    b_slope = (b2.price - b1.price) / max(1, b2.position - b1.position)
    denominator = a_slope - b_slope
    if abs(denominator) <= 1e-12:
        return np.nan
    return (
        b1.price
        - a1.price
        + a_slope * a1.position
        - b_slope * b1.position
    ) / denominator


def _triangle_line_touch_count(
    swings: list[_Swing],
    start_idx: int,
    end_idx: int,
    first_idx: int,
    second_idx: int,
) -> int:
    first = swings[first_idx]
    second = swings[second_idx]
    slope = (second.price - first.price) / max(1, second.position - first.position)
    touches = 0
    for swing in swings[start_idx : end_idx + 1]:
        line_value = first.price + slope * (swing.position - first.position)
        tolerance = 0.25 * swing.atr if np.isfinite(swing.atr) else 0.0
        if abs(swing.price - line_value) <= max(tolerance, 1e-9):
            touches += 1
    return touches


def _triangle_post_e_confirmation(
    swings: list[_Swing],
    b_idx: int,
    d_idx: int,
    e_idx: int,
    end_idx: int,
    source: pd.DataFrame | None,
) -> tuple[bool, int]:
    if end_idx <= e_idx:
        return False, e_idx
    b, d, e = swings[b_idx], swings[d_idx], swings[e_idx]
    slope = (d.price - b.price) / max(1, d.position - b.position)
    upward_break = e.kind == -1
    observations: list[tuple[int, float, int]] = []
    if source is not None and "close" in source:
        last_position = min(swings[end_idx].confirmed_position, len(source) - 1)
        observations.extend(
            (position, float(source["close"].iloc[position]), end_idx)
            for position in range(e.position + 1, last_position + 1)
        )
    else:
        observations.extend(
            (swings[index].position, swings[index].price, index)
            for index in range(e_idx + 1, end_idx + 1)
        )
    for position, price, index in observations:
        line_value = b.price + slope * (position - b.position)
        if (upward_break and price > line_value) or (
            not upward_break and price < line_value
        ):
            return True, index
    return False, e_idx


def _evaluate_simple_correction(
    swings: list[_Swing], start_idx: int, end_idx: int, cfg: ElliottWaveConfig
) -> dict[str, object]:
    """Evaluate source-locked Zig-Zag and Flat candidates in parallel."""

    candidates: list[dict[str, object]] = []
    impulse_counts = cfg.w1_internal_move_counts
    c_motive_counts = tuple(sorted(set((*impulse_counts, 15))))
    correction_counts = (3, 7, 11)
    saw_b_time_failure = False
    saw_c_time_failure = False

    for a_count in impulse_counts:
        for b_count in correction_counts:
            for c_count in c_motive_counts:
                if start_idx + a_count + b_count + c_count != end_idx:
                    continue
                candidate = _correction_ratios(
                    swings, start_idx, a_count, b_count, c_count
                )
                price_pass = (
                    0.01 <= candidate["b_ratio"] <= 0.618
                    and 0.618 <= candidate["c_vs_a"] <= 4.618
                )
                timing = _simple_correction_timing(
                    swings, start_idx, a_count, b_count, end_idx, cfg
                )
                a_diagonal = (
                    _evaluate_diagonal(
                        swings, start_idx, start_idx + a_count, "leading"
                    )
                    if a_count == 21
                    else None
                )
                c_diagonal = (
                    _evaluate_diagonal(
                        swings,
                        start_idx + a_count + b_count,
                        end_idx,
                        "ending",
                    )
                    if c_count == 15
                    else None
                )
                c_structure_pass = c_count != 15 or bool(c_diagonal["confirmed"])
                if price_pass and not timing["b_time_pass"]:
                    saw_b_time_failure = True
                elif price_pass and not timing["c_time_pass"]:
                    saw_c_time_failure = True
                if (
                    price_pass
                    and c_structure_pass
                    and timing["b_time_pass"]
                    and timing["c_time_pass"]
                ):
                    subtype = (
                        "ZIG_ZAG_NORMAL"
                        if candidate["c_vs_a"] <= 1.618
                        else "ZIG_ZAG_ELONGATED"
                    )
                    candidates.append(
                        {
                            **candidate,
                            **timing,
                            "pattern": "Zig-Zag",
                            "subtype": subtype,
                            "fib_error": _nearest_error(
                                float(candidate["b_ratio"]), (0.382, 0.50, 0.618)
                            )
                            + _nearest_error(
                                float(candidate["c_vs_a"]),
                                (1.0, 1.618, 2.618, 4.618),
                            ),
                            "a_structure": (
                                "LEADING_DIAGONAL"
                                if a_diagonal and a_diagonal["confirmed"]
                                else "IMPULSE"
                            ),
                            "c_structure": (
                                "ENDING_DIAGONAL" if c_count == 15 else "IMPULSE"
                            ),
                            "internal_pattern": f"{a_count}-{b_count}-{c_count}",
                            "a_count": a_count,
                            "b_count": b_count,
                            "c_count": c_count,
                            "endpoint_indices": (
                                start_idx + a_count,
                                start_idx + a_count + b_count,
                                end_idx,
                            ),
                        }
                    )

    for a_count in correction_counts:
        for b_count in correction_counts:
            for c_count in c_motive_counts:
                if start_idx + a_count + b_count + c_count != end_idx:
                    continue
                candidate = _correction_ratios(
                    swings, start_idx, a_count, b_count, c_count
                )
                price_pass = (
                    cfg.flat_b_min_retrace <= candidate["b_ratio"] <= cfg.flat_b_max_retrace
                    and 0.618 <= candidate["c_vs_a"] <= 2.618
                )
                timing = _simple_correction_timing(
                    swings, start_idx, a_count, b_count, end_idx, cfg
                )
                c_diagonal = (
                    _evaluate_diagonal(
                        swings,
                        start_idx + a_count + b_count,
                        end_idx,
                        "ending",
                    )
                    if c_count == 15
                    else None
                )
                c_structure_pass = c_count != 15 or bool(c_diagonal["confirmed"])
                if price_pass and not timing["b_time_pass"]:
                    saw_b_time_failure = True
                elif price_pass and not timing["c_time_pass"]:
                    saw_c_time_failure = True
                if (
                    price_pass
                    and c_structure_pass
                    and timing["b_time_pass"]
                    and timing["c_time_pass"]
                ):
                    if candidate["b_ratio"] <= 0.812:
                        subtype = (
                            "FLAT_NORMAL"
                            if candidate["c_vs_a"] <= 1.618
                            else "FLAT_ELONGATED"
                        )
                    else:
                        subtype = (
                            "FLAT_STRONG_IRREGULAR"
                            if candidate["c_vs_a"] <= 1.618
                            else "FLAT_RUNNING"
                        )
                    candidates.append(
                        {
                            **candidate,
                            **timing,
                            "pattern": "Flat",
                            "subtype": subtype,
                            "fib_error": _nearest_error(
                                float(candidate["b_ratio"]),
                                (0.618, 0.812, 1.0, 1.11),
                            )
                            + _nearest_error(
                                float(candidate["c_vs_a"]), (1.0, 1.618, 2.618)
                            ),
                            "a_structure": "CORRECTIVE",
                            "c_structure": (
                                "ENDING_DIAGONAL" if c_count == 15 else "IMPULSE"
                            ),
                            "internal_pattern": f"{a_count}-{b_count}-{c_count}",
                            "a_count": a_count,
                            "b_count": b_count,
                            "c_count": c_count,
                            "endpoint_indices": (
                                start_idx + a_count,
                                start_idx + a_count + b_count,
                                end_idx,
                            ),
                        }
                    )

    if candidates:
        candidates.sort(
            key=lambda candidate: (
                float(candidate["fib_error"]),
                float(candidate["time_error"]),
                int(candidate["a_count"])
                + int(candidate["b_count"])
                + int(candidate["c_count"]),
            )
        )
        primary = candidates[0]
        alternate = candidates[1]["pattern"] if len(candidates) > 1 else ""
        a_idx, b_idx, c_idx = primary["endpoint_indices"]
        channel_type = ""
        channel_target = np.nan
        target_cluster = ""
        if primary["pattern"] == "Zig-Zag":
            origin = swings[start_idx]
            a_point = swings[int(a_idx)]
            b_point = swings[int(b_idx)]
            c_point = swings[int(c_idx)]
            channel_slope = (b_point.price - origin.price) / max(
                1, b_point.position - origin.position
            )
            channel_target = a_point.price + channel_slope * (
                c_point.position - a_point.position
            )
            tolerance = 0.25 * c_point.atr if np.isfinite(c_point.atr) else 0.0
            channel_type = "ZIG_ZAG_0B_PARALLEL_A"
            if abs(c_point.price - channel_target) <= tolerance:
                target_cluster = "FIB_CHANNEL_CLUSTER"
        return {
            "confirmed": True,
            "primary": primary["pattern"],
            "alternate": alternate,
            "subtype": primary["subtype"],
            "b_ratio": primary["b_ratio"],
            "c_vs_a": primary["c_vs_a"],
            "c_vs_b": primary["c_vs_b"],
            "a_count": primary["a_count"],
            "b_count": primary["b_count"],
            "c_count": primary["c_count"],
            "endpoint_indices": primary["endpoint_indices"],
            "labels": ("A", "B", "C"),
            "leg_counts": {
                "A": primary["a_count"],
                "B": primary["b_count"],
                "C": primary["c_count"],
            },
            "internal_pattern": primary["internal_pattern"],
            "internal_count": end_idx - start_idx,
            "reason_code": "CORRECTION_CONFIRMED",
            "mandatory_gate_count": 4,
            "subdivision_score": 3,
            "fib_error": primary["fib_error"],
            "time_error": primary["time_error"],
            "channel_type": channel_type,
            "channel_target": channel_target,
            "target_cluster": target_cluster,
            "time_values": {
                "A": primary["a_duration"],
                "B": primary["b_duration"],
                "C": primary["c_duration"],
            },
            "a_structure": primary["a_structure"],
            "c_structure": primary["c_structure"],
            "note": (
                f"{primary['subtype']} {primary['internal_pattern']} passes; "
                f"B={primary['b_ratio']:.2%}, C/A={primary['c_vs_a']:.2%}; "
                f"A={primary['a_structure']}, C={primary['c_structure']}; "
                f"B/C time gates=PASS."
            ),
        }

    b_ratio = np.nan
    if end_idx - start_idx >= 6:
        a = swings[start_idx + 3]
        b = swings[start_idx + 6]
        b_ratio = _safe_ratio(abs(b.price - a.price), abs(a.price - swings[start_idx].price))
    reason = (
        "FLAT_B_GT_111"
        if np.isfinite(b_ratio) and b_ratio > cfg.flat_b_max_retrace
        else "B_TIME_GATE_FAIL"
        if saw_b_time_failure
        else "C_TIME_GATE_FAIL"
        if saw_c_time_failure
        else "C_INTERNAL_INCOMPLETE"
    )
    return {
        "confirmed": False,
        "primary": "Zig-Zag / Flat",
        "alternate": "",
        "subtype": "SIMPLE_CORRECTION_FORMING",
        "b_ratio": b_ratio,
        "c_vs_a": np.nan,
        "c_vs_b": np.nan,
        "a_count": 0,
        "b_count": 0,
        "c_count": 0,
        "endpoint_indices": (),
        "labels": ("A", "B", "C"),
        "leg_counts": {},
        "internal_pattern": "parallel candidates",
        "internal_count": max(0, end_idx - start_idx),
        "reason_code": reason,
        "note": (
            "Parallel Zig-Zag and Flat candidates remain forming; required "
            "internal counts, Fib gates, or mandatory B/C time gates are incomplete."
        ),
    }


def _simple_correction_timing(
    swings: list[_Swing],
    start_idx: int,
    a_count: int,
    b_count: int,
    end_idx: int,
    cfg: ElliottWaveConfig,
) -> dict[str, object]:
    """Return the V4 mandatory OR time gates for a simple ABC correction."""

    a_idx = start_idx + a_count
    b_idx = a_idx + b_count
    a_duration = max(1, swings[a_idx].position - swings[start_idx].position)
    b_duration = max(1, swings[b_idx].position - swings[a_idx].position)
    c_duration = max(1, swings[end_idx].position - swings[b_idx].position)
    ab_duration = a_duration + b_duration
    b_targets = (
        float(a_duration),
        2.0 * a_duration,
        5.0 * a_duration,
        10.0 * a_duration,
    )
    c_targets = (0.25 * ab_duration, 0.50 * ab_duration, float(ab_duration))
    return {
        "a_duration": a_duration,
        "b_duration": b_duration,
        "c_duration": c_duration,
        "b_time_pass": _matches_absolute_time_targets(
            b_duration, b_targets, cfg.time_tolerance_bars
        ),
        "c_time_pass": _matches_absolute_time_targets(
            c_duration, c_targets, cfg.time_tolerance_bars
        ),
        "time_error": min(abs(b_duration - target) for target in b_targets)
        + min(abs(c_duration - target) for target in c_targets),
    }


def _correction_ratios(
    swings: list[_Swing],
    start_idx: int,
    a_count: int,
    b_count: int,
    c_count: int,
) -> dict[str, float]:
    start = swings[start_idx]
    a = swings[start_idx + a_count]
    b = swings[start_idx + a_count + b_count]
    c = swings[start_idx + a_count + b_count + c_count]
    a_length = abs(a.price - start.price)
    b_length = abs(b.price - a.price)
    c_length = abs(c.price - b.price)
    return {
        "b_ratio": _safe_ratio(b_length, a_length),
        "c_vs_a": _safe_ratio(c_length, a_length),
        "c_vs_b": _safe_ratio(c_length, b_length),
    }


def _directional_retrace(p0: float, p1: float, current: float, bullish: bool) -> float:
    wave1 = abs(p1 - p0)
    return _safe_ratio(p1 - current if bullish else current - p1, wave1)


def _duration_ratio(
    start: _Swing, end: _Swing, reference_start: _Swing, reference_end: _Swing
) -> float:
    duration = max(1, end.position - start.position)
    reference = max(1, reference_end.position - reference_start.position)
    return duration / reference


def _matches_time_window(
    observed: int | float,
    references: tuple[int | float, ...],
    multipliers: tuple[float, ...],
    tolerance_bars: int,
) -> bool:
    targets = tuple(float(reference) * multiplier for reference in references for multiplier in multipliers)
    return _matches_absolute_time_targets(observed, targets, tolerance_bars)


def _matches_absolute_time_targets(
    observed: int | float, targets: tuple[float, ...], tolerance_bars: int
) -> bool:
    return any(abs(float(observed) - target) <= tolerance_bars for target in targets)


def _nearest_error(value: float, targets: tuple[float, ...]) -> float:
    if not np.isfinite(value):
        return float("inf")
    return min(abs(value - target) for target in targets)


def _flat_a_minimum_pass(
    correction: dict[str, object],
    swings: list[_Swing],
    start_idx: int,
    preceding_length: float,
    cfg: ElliottWaveConfig,
) -> bool:
    if correction.get("primary") != "Flat":
        return True
    endpoints = tuple(correction.get("endpoint_indices", ()))
    if not endpoints:
        return False
    a_length = abs(swings[int(endpoints[0])].price - swings[start_idx].price)
    a_ratio = _safe_ratio(a_length, preceding_length)
    return bool(np.isfinite(a_ratio) and a_ratio >= cfg.flat_a_min_retrace)


def _w2_minimum(cfg: ElliottWaveConfig) -> float:
    return cfg.wave2_min_retrace if cfg.wave2_minimum_mode == "Chartking" else 0.14


def _w4_minimum(cfg: ElliottWaveConfig) -> float:
    if cfg.wave4_minimum_mode == "Chartking":
        return cfg.wave4_min_retrace
    return 0.14


def _w3_maximum(cfg: ElliottWaveConfig) -> float:
    return cfg.wave3_max_extension if cfg.wave3_maximum_mode == "Chartking 2700%" else 21.0


def _internal_four_overlaps_one(
    swings: list[_Swing], start_idx: int, end_idx: int, bullish: bool
) -> bool:
    if end_idx - start_idx < 5:
        return False
    wave1_internal = swings[start_idx + 1]
    wave4_internal = swings[end_idx - 1]
    return (
        wave4_internal.price <= wave1_internal.price
        if bullish
        else wave4_internal.price >= wave1_internal.price
    )


def _evaluate_diagonal(
    swings: list[_Swing], start_idx: int, end_idx: int, kind: str
) -> dict[str, object]:
    """Classify a source-locked leading or ending diagonal container."""

    if kind not in {"leading", "ending"}:
        raise ValueError("kind must be 'leading' or 'ending'")
    leg_counts = (5, 3, 5, 3, 5) if kind == "leading" else (3, 3, 3, 3, 3)
    if end_idx - start_idx != sum(leg_counts):
        return {"confirmed": False, "reason_code": "DIAGONAL_INTERNAL_FAIL"}

    endpoints: list[int] = []
    cursor = start_idx
    for count in leg_counts:
        cursor += count
        endpoints.append(cursor)
    p0, p1, p2, p3, p4, p5 = (
        swings[index] for index in (start_idx, *endpoints)
    )
    bullish = p0.kind == -1 and p5.kind == 1 and p5.price > p0.price
    bearish = p0.kind == 1 and p5.kind == -1 and p5.price < p0.price
    if not (bullish or bearish):
        return {"confirmed": False, "reason_code": "DIAGONAL_DIRECTION_FAIL"}

    advances = (
        p3.price > p1.price and p5.price > p3.price and p4.price > p2.price
        if bullish
        else p3.price < p1.price and p5.price < p3.price and p4.price < p2.price
    )
    overlap = p4.price <= p1.price if bullish else p4.price >= p1.price
    wave2_boundary = p4.price > p2.price if bullish else p4.price < p2.price
    early_width = abs(p1.price - p2.price)
    late_width = abs(p3.price - p4.price)
    wedge = advances and not np.isclose(early_width, late_width)
    wedge_subtype = "CONTRACTING" if late_width < early_width else "EXPANDING"
    divergence = (
        p5.macd_hist < p3.macd_hist
        if bullish
        else p5.macd_hist > p3.macd_hist
    )
    w1_length = abs(p1.price - p0.price)
    w3_ratio = _safe_ratio(abs(p3.price - p2.price), w1_length)
    w4_retrace = _safe_ratio(abs(p3.price - p4.price), abs(p3.price - p0.price))
    w5_ratio = _safe_ratio(abs(p5.price - p4.price), w1_length)
    leading_fib_pass = bool(
        np.isfinite(w3_ratio)
        and 0.618 - 1e-9 <= w3_ratio < 1.618 - 1e-9
        and np.isfinite(w4_retrace)
        and 0.236 - 1e-9 <= w4_retrace <= 0.618 + 1e-9
        and np.isfinite(w5_ratio)
        and (
            1.618 - 1e-9 <= w5_ratio <= 2.618 + 1e-9
            or abs(w5_ratio - 1.0) <= 0.02
        )
    )
    confirmed = bool(
        overlap
        and wave2_boundary
        and wedge
        and (leading_fib_pass if kind == "leading" else divergence)
    )
    reason = (
        "DIAGONAL_CONFIRMED"
        if confirmed
        else "DIAGONAL_OVERLAP_FAIL"
        if not overlap or not wave2_boundary
        else "DIAGONAL_WEDGE_FAIL"
        if not wedge
        else "LEADING_DIAGONAL_FIB_FAIL"
        if kind == "leading" and not leading_fib_pass
        else "ENDING_DIAGONAL_DIVERGENCE_FAIL"
    )
    return {
        "confirmed": confirmed,
        "kind": kind.upper(),
        "subtype": f"{kind.upper()}_DIAGONAL_{wedge_subtype}",
        "reason_code": reason,
        "leg_counts": leg_counts,
        "endpoint_indices": tuple(endpoints),
        "internal_pattern": "-".join(str(count) for count in leg_counts),
        "bullish": bullish,
        "overlap": overlap,
        "wave2_boundary_pass": wave2_boundary,
        "wedge": wedge,
        "divergence": divergence,
        "w3_ratio": w3_ratio,
        "w4_retrace": w4_retrace,
        "w5_ratio": w5_ratio,
        "invalidation_price": p4.price,
    }


def _impulse_channel_evidence(
    p2: _Swing,
    p3: _Swing,
    p4: _Swing,
    p5: _Swing,
    bullish: bool,
    divergence: bool,
    cfg: ElliottWaveConfig,
) -> dict[str, object]:
    """Evaluate the locked 2-4 channel, parallel-through-3 target and FBO clue."""

    slope = (p4.price - p2.price) / max(1, p4.position - p2.position)
    lower_value = p2.price + slope * (p5.position - p2.position)
    channel_target = p3.price + slope * (p5.position - p3.position)
    projection_base = abs(p3.price - p4.price)
    direction = 1.0 if bullish else -1.0
    fib_targets = (
        p4.price + direction * cfg.wave5_min_extension * projection_base,
        p4.price + direction * cfg.wave5_max_extension * projection_base,
    )
    tolerance = 0.25 * p5.atr if np.isfinite(p5.atr) else 0.0
    cluster = any(abs(channel_target - target) <= tolerance for target in fib_targets)
    beyond_action = (
        p5.price > channel_target + tolerance
        if bullish
        else p5.price < channel_target - tolerance
    )
    fbd_candidate = "FBO_BASE_CANDIDATE" if beyond_action and divergence else ""
    channel_contact = abs(p5.price - channel_target) <= tolerance
    confidence = 70.0
    confidence += 10.0 if divergence else 0.0
    confidence += 10.0 if cluster else 0.0
    confidence += 10.0 if channel_contact else 0.0
    return {
        "channel_type": "IMPULSE_2_4_PARALLEL_3",
        "channel_target": channel_target,
        "channel_lower": lower_value,
        "target_cluster": "FIB_CHANNEL_CLUSTER" if cluster else "",
        "fbd_candidate": fbd_candidate,
        "confidence": confidence,
        "support_evidence": (
            "CHANNEL_CONTACT" if channel_contact else "CHANNEL_PROJECTION"
        ),
    }


def _candidate_ending_at(
    swings: list[_Swing],
    processed_indices: list[int],
    end_idx: int,
    search_floor: int,
    cfg: ElliottWaveConfig,
    source: pd.DataFrame | None,
    locked_start_idx: int | None = None,
) -> dict[str, object] | None:
    processed_set = set(processed_indices)
    candidates: list[dict[str, object]] = []
    for internal_count in cfg.w1_internal_move_counts:
        start_idx = end_idx - internal_count
        if start_idx < 0 or start_idx not in processed_set:
            continue
        if locked_start_idx is not None and start_idx != locked_start_idx:
            continue
        start = swings[start_idx]
        end = swings[end_idx]
        if start.position < search_floor or start.kind == end.kind:
            continue
        bullish = start.kind == -1 and end.kind == 1 and end.price > start.price
        bearish = start.kind == 1 and end.kind == -1 and end.price < start.price
        if not (bullish or bearish):
            continue
        if not _anchor_direction_ok(start, bullish, cfg):
            continue

        development = _w1_development_evidence(
            swings, start_idx, end_idx, bullish, cfg, source
        )
        degree_progress = float(development["degree_progress"])
        degree_ok = bool(development["degree_pass"])
        time_ok = bool(development["time_pass"])
        significant_ok = bool(
            start.degree_significant
            or start.important_extreme
            or (search_floor >= 0 and start.position == search_floor)
        )
        important_ok = cfg.wave1_start_mode == "Off" or significant_ok
        distance = abs(end.price - start.price)
        atr_ok = cfg.important_atr_multiple <= 0 or (
            np.isfinite(start.atr) and distance >= start.atr * cfg.important_atr_multiple
        )
        oscillator_ok, oscillator_note = _oscillator_evidence(
            swings, start_idx, bullish, cfg
        )
        if not (degree_ok and time_ok and important_ok and atr_ok):
            continue
        if _candidate_crosses_origin(
            swings, start_idx, end_idx, bullish, source, end.confirmed_position
        ):
            continue

        leading_diagonal = (
            _evaluate_diagonal(swings, start_idx, end_idx, "leading")
            if internal_count == 21
            else None
        )
        subtype = (
            str(leading_diagonal["subtype"])
            if leading_diagonal and leading_diagonal["confirmed"]
            else "EXTENDED_W1"
            if internal_count > 5
            else "NORMAL_W1"
        )
        pattern = "Leading Diagonal" if "LEADING_DIAGONAL" in subtype else "Motive"

        candidates.append({
            "start_idx": start_idx,
            "end_idx": end_idx,
            "bullish": bullish,
            "base_price": start.price,
            "base_position": start.position,
            "degree_progress": degree_progress,
            "development_position": int(development["development_position"]),
            "development_index": development["development_index"],
            "development_level": float(development["development_level"]),
            "w1_time_ratio": float(development["time_ratio"]),
            "w1_time_rule": str(development["time_rule"]),
            "internal_count": internal_count,
            "pattern": pattern,
            "subtype": subtype,
            "internal_pattern": (
                str(leading_diagonal["internal_pattern"])
                if leading_diagonal and leading_diagonal["confirmed"]
                else "5/9/13/17/21-move impulse"
            ),
            "note": (
                f"Wave 1 {subtype} confirmed with {internal_count} internal moves and "
                f"{degree_progress:.2%} maximum degree development; "
                f"{development['time_rule']}; {oscillator_note} "
                f"({'support' if oscillator_ok else 'no oscillator support'})."
            ),
            "_rank": (
                int(start.important_extreme),
                int(oscillator_ok),
                int(start.degree_significant),
                internal_count,
                -start.position,
            ),
        })
    if not candidates:
        return None
    selected = max(candidates, key=lambda candidate: tuple(candidate["_rank"]))
    selected.pop("_rank", None)
    return selected


def _w1_development_evidence(
    swings: list[_Swing],
    start_idx: int,
    end_idx: int,
    bullish: bool,
    cfg: ElliottWaveConfig,
    source: pd.DataFrame | None,
    through_position: int | None = None,
) -> dict[str, object]:
    """Separate the closed 61.8% degree event from the later W1 terminal pivot."""

    start = swings[start_idx]
    end = swings[end_idx]
    opposite_price = start.important_high if bullish else start.important_low
    degree_range = abs(opposite_price - start.price)
    development_level = start.price + (
        cfg.degree_retrace * degree_range * (1.0 if bullish else -1.0)
    )
    full_level = start.price + degree_range * (1.0 if bullish else -1.0)

    observations: list[tuple[int, object, float, float]] = []
    if source is not None:
        last_position = min(
            end.confirmed_position if through_position is None else through_position,
            len(source) - 1,
        )
        for position in range(start.position + 1, last_position + 1):
            observations.append(
                (
                    position,
                    source.index[position],
                    float(source["high"].iloc[position]),
                    float(source["low"].iloc[position]),
                )
            )
    else:
        for swing in swings[start_idx + 1 : end_idx + 1]:
            observations.append(
                (swing.position, swing.index, swing.price, swing.price)
            )

    development_position: int | None = None
    development_index: object = end.confirmed_index
    full_position: int | None = None
    maximum_excursion = 0.0
    for position, index, observed_high, observed_low in observations:
        excursion = (
            observed_high - start.price if bullish else start.price - observed_low
        )
        maximum_excursion = max(maximum_excursion, excursion)
        touched = observed_high >= development_level if bullish else observed_low <= development_level
        touched_full = observed_high >= full_level if bullish else observed_low <= full_level
        if touched and development_position is None:
            development_position = position
            development_index = index
        if touched_full and full_position is None:
            full_position = position

    degree_progress = _safe_ratio(maximum_excursion, degree_range)
    prior_extreme_position = (
        start.important_high_position if bullish else start.important_low_position
    )
    prior_duration = (
        start.position - int(prior_extreme_position)
        if prior_extreme_position is not None
        else 0
    )
    touch_duration = (
        int(development_position) - start.position
        if development_position is not None
        else 0
    )
    full_duration = (
        int(full_position) - start.position if full_position is not None else 0
    )
    half_time_pass = bool(
        prior_duration > 0
        and development_position is not None
        and abs(touch_duration - 0.50 * prior_duration) <= cfg.time_tolerance_bars
    )
    full_time_pass = bool(
        prior_duration > 0
        and full_position is not None
        and abs(full_duration - prior_duration) <= cfg.time_tolerance_bars
    )
    time_pass = half_time_pass or full_time_pass
    time_ratio = _safe_ratio(touch_duration, prior_duration)
    time_rule = (
        "W1_TIME_61_8_AT_HALF"
        if half_time_pass
        else "W1_TIME_100_AT_EQUAL"
        if full_time_pass
        else "W1_TIME_GATE_FAIL"
    )
    return {
        "degree_pass": development_position is not None,
        "degree_progress": degree_progress,
        "development_position": (
            development_position if development_position is not None else end.position
        ),
        "development_index": development_index,
        "development_level": development_level,
        "time_pass": time_pass,
        "time_ratio": time_ratio,
        "time_rule": time_rule,
    }


def _best_developed_base(
    swings: list[_Swing],
    processed_indices: list[int],
    through_position: int,
    search_floor: int,
    cfg: ElliottWaveConfig,
    source: pd.DataFrame | None,
) -> dict[str, object] | None:
    """Select Point 0 when development closes, before a W1 terminal exists."""

    if not processed_indices:
        return None
    end_idx = processed_indices[-1]
    candidates: list[dict[str, object]] = []
    for start_idx in processed_indices:
        start = swings[start_idx]
        if start.position < search_floor or start.confirmed_position > through_position:
            continue
        significant = bool(
            cfg.wave1_start_mode == "Off"
            or start.degree_significant
            or start.important_extreme
            or (search_floor >= 0 and start.position == search_floor)
        )
        if not significant:
            continue
        bullish = start.kind == -1
        if not _anchor_direction_ok(start, bullish, cfg):
            continue
        development = _w1_development_evidence(
            swings,
            start_idx,
            end_idx,
            bullish,
            cfg,
            source,
            through_position=through_position,
        )
        if not (development["degree_pass"] and development["time_pass"]):
            continue
        if _candidate_crosses_origin(
            swings, start_idx, end_idx, bullish, source, through_position
        ):
            continue
        oscillator_support, oscillator_note = _oscillator_evidence(
            swings, start_idx, bullish, cfg
        )
        candidates.append(
            {
                "start_idx": start_idx,
                "end_idx": start_idx,
                "bullish": bullish,
                "base_price": start.price,
                "base_position": start.position,
                "degree_progress": float(development["degree_progress"]),
                "development_position": int(development["development_position"]),
                "development_index": development["development_index"],
                "development_level": float(development["development_level"]),
                "w1_time_ratio": float(development["time_ratio"]),
                "w1_time_rule": str(development["time_rule"]),
                "internal_count": 0,
                "pattern": "Motive",
                "subtype": "W1_DEVELOPED",
                "internal_pattern": "Awaiting 5/9/13/17/21 terminal",
                "oscillator_note": oscillator_note,
                "_rank": (
                    int(start.important_extreme),
                    int(oscillator_support),
                    int(start.degree_significant),
                    -start.position,
                ),
            }
        )
    if not candidates:
        return None
    selected = max(candidates, key=lambda candidate: tuple(candidate["_rank"]))
    selected.pop("_rank", None)
    return selected


def _anchor_direction_ok(start: _Swing, bullish: bool, cfg: ElliottWaveConfig) -> bool:
    return bool(
        cfg.anchor_direction == "Auto"
        or (
            cfg.anchor_direction == "Bullish from important low"
            and start.kind == -1
            and bullish
        )
        or (
            cfg.anchor_direction == "Bearish from important high"
            and start.kind == 1
            and not bullish
        )
    )


def _oscillator_evidence(
    swings: list[_Swing], start_idx: int, bullish: bool, cfg: ElliottWaveConfig
) -> tuple[bool, str]:
    start = swings[start_idx]
    previous = _previous_same_type_swing(swings, start_idx, start.kind)
    divergence = False
    if previous is not None:
        price_extends = start.price < previous.price if bullish else start.price > previous.price
        rsi_diverges = start.rsi > previous.rsi if bullish else start.rsi < previous.rsi
        macd_diverges = (
            start.macd_hist > previous.macd_hist
            if bullish
            else start.macd_hist < previous.macd_hist
        )
        divergence = bool(price_extends and (rsi_diverges or macd_diverges))

    extreme = bool(start.macd_extreme)
    mode = cfg.base_oscillator_mode
    passed = {
        "Extreme or divergence": extreme or divergence,
        "Extreme only": extreme,
        "Divergence only": divergence,
        "Extreme and divergence": extreme and divergence,
        "Off": True,
    }[mode]
    return bool(passed), (
        f"base oscillator extreme={'yes' if extreme else 'no'}, "
        f"divergence={'yes' if divergence else 'no'}"
    )


def _candidate_crosses_origin(
    swings: list[_Swing],
    start_idx: int,
    end_idx: int,
    bullish: bool,
    source: pd.DataFrame | None,
    through_position: int,
) -> bool:
    base_price = swings[start_idx].price
    for swing in swings[start_idx + 1 : end_idx + 1]:
        if bullish and swing.kind == -1 and swing.price <= base_price:
            return True
        if not bullish and swing.kind == 1 and swing.price >= base_price:
            return True
    if source is None:
        return False
    start_position = swings[start_idx].position + 1
    end_position = min(through_position, len(source) - 1)
    if end_position < start_position:
        return False
    segment = source.iloc[start_position : end_position + 1]
    if bullish:
        return bool((segment["low"].astype(float) <= base_price).any())
    return bool((segment["high"].astype(float) >= base_price).any())


def _origin_break_position(
    source: pd.DataFrame | None,
    active: dict[str, object],
    swings: list[_Swing],
    start_position: int,
    end_position: int,
) -> int | None:
    base_price = float(active["base_price"])
    bullish = bool(active["bullish"])
    if source is not None:
        start_position = max(0, start_position)
        end_position = min(end_position, len(source) - 1)
        if end_position < start_position:
            return None
        segment = source.iloc[start_position : end_position + 1]
        values = segment["low"].astype(float) if bullish else segment["high"].astype(float)
        broken = values <= base_price if bullish else values >= base_price
        if broken.any():
            first_index = broken[broken].index[0]
            return int(source.index.get_loc(first_index))
        return None

    for swing in swings:
        if swing.confirmed_position < start_position or swing.confirmed_position > end_position:
            continue
        if bullish and swing.price <= base_price:
            return swing.position
        if not bullish and swing.price >= base_price:
            return swing.position
    return None

def _correction_count(cfg: ElliottWaveConfig) -> int:
    if cfg.correction_pattern in {"W-X-Y-X-Z", "W-X-Y-XX-Z", "A-B-C-D-E"}:
        return 5
    return 3


def _cycle_length(cfg: ElliottWaveConfig) -> int:
    return (8 if cfg.show_wave4_internal else 6) + _correction_count(cfg)


def _wave4_phase(cfg: ElliottWaveConfig) -> int:
    return 6 if cfg.show_wave4_internal else 4


def _wave5_phase(cfg: ElliottWaveConfig) -> int:
    return 7 if cfg.show_wave4_internal else 5


def _phase_for_index(
    swings: list[_Swing], wave_index: int, cfg: ElliottWaveConfig
) -> int | None:
    cycle_length = _cycle_length(cfg)
    if cfg.count_mode == "All swings":
        return wave_index % cycle_length
    anchor = _valid_anchor_index(swings, wave_index, cfg)
    if anchor is None:
        return None
    return (wave_index - anchor) % cycle_length


def _valid_anchor_index(
    swings: list[_Swing], wave_index: int, cfg: ElliottWaveConfig
) -> int | None:
    anchor = None
    for candidate in range(wave_index + 1):
        confirmed, _ = _wave1_start_state(swings, candidate, cfg)
        if confirmed:
            anchor = candidate
    return anchor


def _correction_label(offset: int, cfg: ElliottWaveConfig) -> str:
    correction_labels = {
        "A-B-C": {0: "(A)", 1: "(B)", 2: "(C)"},
        "W-X-Y": {0: "W", 1: "X", 2: "Y"},
        "W-X-Y-X-Z": {0: "W", 1: "X", 2: "Y", 3: "XX", 4: "Z"},
        "W-X-Y-XX-Z": {0: "W", 1: "X", 2: "Y", 3: "XX", 4: "Z"},
        "A-B-C-D-E": {0: "(A)", 1: "(B)", 2: "(C)", 3: "(D)", 4: "(E)"},
    }
    return correction_labels[cfg.correction_pattern][offset]


def _phase_label(phase: int, cfg: ElliottWaveConfig) -> str:
    if cfg.show_wave4_internal:
        if phase <= 3:
            return "0" if phase == 0 else str(phase)
        if phase == 4:
            return "(A)"
        if phase == 5:
            return "(B)"
        if phase == 6:
            return "4\n(C)"
        if phase == 7:
            return "5"
        return _correction_label(phase - 8, cfg)
    if phase <= 5:
        return "0" if phase == 0 else str(phase)
    return _correction_label(phase - 6, cfg)

def _rule_state(
    swings: list[_Swing], wave_index: int, cfg: ElliottWaveConfig, phase: int, cycle_start: int
) -> tuple[str, str, object, float, float]:
    duration = _wave_duration(swings, wave_index)
    wave4_phase = _wave4_phase(cfg)
    wave5_phase = _wave5_phase(cfg)
    if cycle_start < 0:
        return "ok", "", None, duration, np.nan

    if phase == 1 and wave_index >= 1:
        confirmed, note = _wave1_start_state(swings, cycle_start, cfg)
        return _state(False, not confirmed), note, confirmed, duration, np.nan

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
        ), None, duration, time_ratio

    if phase == 3 and wave_index >= 3:
        p0, p1, p2, p3 = (swings[cycle_start + offset].price for offset in range(4))
        t0, t1, t2, t3 = (swings[cycle_start + offset].position for offset in range(4))
        ratio = _safe_ratio(abs(p3 - p2), abs(p1 - p0))
        time1 = max(1, t1 - t0)
        time2 = max(1, t2 - t1)
        time3 = max(1, t3 - t2)
        equal12 = abs(time1 - time2) <= time1 * 0.05
        expected3 = time1 + time2 if equal12 else (time1 + time2) / 2.0
        time_ratio = _safe_ratio(time3, expected3)
        time_warning = abs(time_ratio - 1.0) > cfg.diagnostic_time_tolerance_ratio
        warning = ratio < cfg.wave3_min_extension or time_warning
        return _state(False, warning), (
            f"Wave 3={ratio:.2%} of Wave 1, time={time3} bars vs rule {expected3:.2f}"
        ), None, duration, time_ratio

    if cfg.show_wave4_internal and phase == 4 and wave_index >= 4:
        p2 = swings[cycle_start + 2].price
        p3 = swings[cycle_start + 3].price
        p_a = swings[cycle_start + 4].price
        retrace = _safe_ratio(abs(p3 - p_a), abs(p3 - p2))
        warning = retrace < cfg.flat_a_min_retrace
        return _state(False, warning), (
            f"Wave 4 A retrace={retrace:.2%} of W3, flat minimum={cfg.flat_a_min_retrace:.2%}"
        ), None, duration, retrace

    if cfg.show_wave4_internal and phase == 5 and wave_index >= 5:
        p3 = swings[cycle_start + 3].price
        p_a = swings[cycle_start + 4].price
        p_b = swings[cycle_start + 5].price
        b_retrace = _safe_ratio(abs(p_b - p_a), abs(p3 - p_a))
        warning = b_retrace < cfg.flat_b_min_retrace or b_retrace > cfg.flat_b_max_retrace
        return _state(False, warning), (
            f"B wave={b_retrace:.2%} of A, flat range={cfg.flat_b_min_retrace:.2%}-{cfg.flat_b_max_retrace:.2%}"
        ), None, duration, b_retrace

    if phase == wave4_phase and wave_index >= wave4_phase:
        p1 = swings[cycle_start + 1].price
        p2 = swings[cycle_start + 2].price
        p3 = swings[cycle_start + 3].price
        p4 = swings[cycle_start + wave4_phase].price
        t1 = swings[cycle_start + 1].position
        t2 = swings[cycle_start + 2].position
        t3 = swings[cycle_start + 3].position
        t4 = swings[cycle_start + wave4_phase].position
        bullish = p3 > p2
        retrace = _safe_ratio(abs(p3 - p4), abs(p3 - p2))
        time2 = max(1, t2 - t1)
        time4 = max(1, t4 - t3)
        time_ratio = _safe_ratio(time4, time2)
        time_warning = not _near_any(
            time_ratio, (0.5, 2.0, 3.0), cfg.diagnostic_time_tolerance_ratio
        )
        invalid = p4 <= p1 if bullish else p4 >= p1
        warning = retrace < cfg.wave4_min_retrace or retrace > cfg.wave4_max_retrace or time_warning
        label = "Wave 4/C" if cfg.show_wave4_internal else "Wave 4"
        return _state(invalid, warning), (
            f"{label} retrace={retrace:.2%}, time={time_ratio:.2f}x W2, correction={cfg.correction_pattern}"
        ), None, duration, time_ratio

    if phase == wave5_phase and wave_index >= wave5_phase:
        p0 = swings[cycle_start].price
        p1 = swings[cycle_start + 1].price
        p2 = swings[cycle_start + 2].price
        p3 = swings[cycle_start + 3].price
        p4 = swings[cycle_start + wave4_phase].price
        p5 = swings[cycle_start + wave5_phase].price
        wave1 = abs(p1 - p0)
        wave3 = abs(p3 - p2)
        wave5 = abs(p5 - p4)
        ratio = _safe_ratio(wave5, abs(p3 - p4))
        invalid = wave3 < wave1 and wave3 < wave5
        warning = ratio < cfg.wave5_min_extension or ratio > cfg.wave5_max_extension
        return _state(invalid, warning), f"Wave 5={ratio:.2%} of Wave 3-4", None, duration, np.nan

    return "ok", "", None, duration, np.nan

def _wave1_start_state(
    swings: list[_Swing], cycle_start: int, cfg: ElliottWaveConfig
) -> tuple[bool, str]:
    if cfg.wave1_start_mode == "Off":
        return True, ""
    if cycle_start + 1 >= len(swings):
        return False, "Wave 1 start: waiting for next pivot"

    start = swings[cycle_start]
    wave1 = swings[cycle_start + 1]
    distance = abs(wave1.price - start.price)
    degree_ok = np.isfinite(start.important_range) and start.important_range > 0 and distance >= start.important_range * cfg.degree_retrace
    atr_ok = cfg.important_atr_multiple <= 0 or (
        np.isfinite(start.atr) and distance >= start.atr * cfg.important_atr_multiple
    )
    bullish_start = wave1.price > start.price
    direction_ok = (
        cfg.anchor_direction == "Auto"
        or (cfg.anchor_direction == "Bullish from important low" and start.kind == -1 and bullish_start)
        or (cfg.anchor_direction == "Bearish from important high" and start.kind == 1 and not bullish_start)
    )
    important_ok = bool(direction_ok and start.important_extreme and degree_ok and atr_ok)
    previous = _previous_same_type_swing(swings, cycle_start, start.kind)
    divergence_ok = False
    if previous is not None:
        price_extends = start.price < previous.price if bullish_start else start.price > previous.price
        rsi_diverges = start.rsi > previous.rsi if bullish_start else start.rsi < previous.rsi
        macd_diverges = start.macd_hist > previous.macd_hist if bullish_start else start.macd_hist < previous.macd_hist
        divergence_ok = bool(price_extends and (rsi_diverges or macd_diverges))

    oscillator_ok = bool(start.macd_extreme or divergence_ok)
    confirmed = important_ok
    if cfg.wave1_start_mode == "Important swing + oscillator":
        confirmed = important_ok and oscillator_ok

    note = (
        "Wave 1 start: direction "
        f"{'OK' if direction_ok else 'no'}, Important H/L "
        f"{'OK' if start.important_extreme else 'no'}, degree "
        f"{'OK' if degree_ok else 'no'}, ATR swing "
        f"{'OK' if atr_ok else 'weak'}, MACD extreme "
        f"{'OK' if start.macd_extreme else 'no'}, RSI/MACD divergence "
        f"{'OK' if divergence_ok else 'no'}"
    )
    return bool(confirmed), note


def _previous_same_type_swing(
    swings: list[_Swing], index: int, kind: int
) -> _Swing | None:
    for candidate in reversed(swings[:index]):
        if candidate.kind == kind:
            return candidate
    return None




def _anchor_fib_price(anchor: _Swing, ratio: float) -> float:
    important_range = anchor.important_high - anchor.important_low
    if not np.isfinite(important_range) or important_range <= 0:
        return np.nan
    if anchor.kind == -1:
        return anchor.important_low + important_range * ratio
    return anchor.important_high - important_range * ratio

def _wave_duration(swings: list[_Swing], wave_index: int) -> float:
    if wave_index <= 0:
        return np.nan
    return float(max(1, swings[wave_index].position - swings[wave_index - 1].position))


def _wave5_targets(
    swings: list[_Swing], wave_index: int, cfg: ElliottWaveConfig
) -> tuple[float, float]:
    phase = _phase_for_index(swings, wave_index, cfg)
    if phase is None:
        return np.nan, np.nan
    cycle_start = wave_index - phase
    wave4_phase = _wave4_phase(cfg)
    if cycle_start < 0 or cycle_start + wave4_phase >= len(swings):
        return np.nan, np.nan
    p3 = swings[cycle_start + 3].price
    p4 = swings[cycle_start + wave4_phase].price
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



def _near_any(value: float, targets: tuple[float, ...], tolerance: float) -> bool:
    if np.isnan(value):
        return False
    return any(abs(value - target) <= tolerance for target in targets)

def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0 or np.isnan(denominator):
        return np.nan
    return numerator / denominator


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.astype(float).ewm(span=length, adjust=False).mean()


def _rma(series: pd.Series, length: int) -> pd.Series:
    values = series.astype(float).to_numpy()
    output = np.full(len(values), np.nan, dtype=float)
    valid_positions = np.flatnonzero(~np.isnan(values))
    if len(valid_positions) < length:
        return pd.Series(output, index=series.index)

    seed_positions = valid_positions[:length]
    seed_position = int(seed_positions[-1])
    output[seed_position] = float(np.mean(values[seed_positions]))
    for position in range(seed_position + 1, len(values)):
        previous = output[position - 1]
        current = values[position]
        if np.isnan(previous):
            output[position] = current
        elif np.isnan(current):
            output[position] = previous
        else:
            output[position] = (previous * (length - 1) + current) / length
    return pd.Series(output, index=series.index)
