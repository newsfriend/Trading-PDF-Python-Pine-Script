"""State-based Elliott Wave overlay engine.

The confirmed pivot/ATR layer is only a raw market-structure provider.  Main
Elliott labels are emitted by a persistent candidate lifecycle so that a new
minor pivot cannot advance or restart the main-degree count by itself.

The source-locked candidate engine implements the P0 foundation, the core
Wave 1-5 impulse sequence, and the mandatory transition into a larger A-B-C
correction container. Labels are promoted only after their structure gates
pass; raw pivots never advance the main count by position or modulo arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    min_swing_atr_multiple: float = 1.5
    min_swing_range_pct: float = 0.03
    correction_pattern: str = "A-B-C"
    show_wave4_internal: bool = True
    count_mode: str = "Validated Anchor"
    wave1_start_mode: str = "Important swing + oscillator"
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


def compute_elliott_waves(
    candles: pd.DataFrame, config: ElliottWaveConfig | None = None
) -> pd.DataFrame:
    """Return OHLC data with Elliott Wave labels on confirmed swing pivots."""

    cfg = config or ElliottWaveConfig()
    _validate_config(cfg)
    source = _with_indicators(_normalize_ohlc(candles), cfg)
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
    if cfg.important_context_mode not in {"Calendar days", "Legacy bars"}:
        raise ValueError('important_context_mode must be "Calendar days" or "Legacy bars"')
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
    valid_patterns = {"A-B-C", "W-X-Y", "W-X-Y-X-Z", "A-B-C-D-E"}
    if cfg.correction_pattern not in valid_patterns:
        raise ValueError(f"correction_pattern must be one of {sorted(valid_patterns)}")
    valid_start_modes = {"Off", "Important swing", "Important swing + oscillator"}
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
    if cfg.degree_retrace <= 0:
        raise ValueError("degree_retrace must be greater than 0")
    if not 0 < cfg.wave2_min_retrace <= cfg.wave2_max_retrace < 1:
        raise ValueError("Wave 2 normal retracement must be inside (0, 1)")
    if not 0 < cfg.wave4_min_retrace <= cfg.wave4_max_retrace < 1:
        raise ValueError("Wave 4 normal retracement must be inside (0, 1)")
    if cfg.wave3_terminal_min_extension <= 0 or cfg.wave3_min_extension <= 0:
        raise ValueError("Wave 3 extension thresholds must be positive")
    if cfg.flat_b_max_retrace < cfg.flat_b_min_retrace:
        raise ValueError("flat_b_max_retrace must be greater than or equal to flat_b_min_retrace")
    if cfg.time_tolerance_bars < 0:
        raise ValueError("time_tolerance_bars cannot be negative")


def _normalize_ohlc(candles: pd.DataFrame) -> pd.DataFrame:
    normalized = candles.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    missing = [column for column in ("high", "low", "close") if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required OHLC columns: {missing}")
    return normalized.sort_index()


def _with_indicators(source: pd.DataFrame, cfg: ElliottWaveConfig) -> pd.DataFrame:
    enriched = source.copy()
    close = enriched["close"].astype(float)
    high = enriched["high"].astype(float)
    low = enriched["low"].astype(float)

    if cfg.important_context_mode == "Calendar days":
        if not isinstance(enriched.index, pd.DatetimeIndex):
            raise ValueError(
                "A DatetimeIndex is required for Calendar days Important H/L context. "
                "Use important_context_mode='Legacy bars' only for compatibility data."
            )
        window = f"{cfg.important_lookback_days}D"
        enriched["_ew_important_high"] = high.rolling(window, min_periods=1).max()
        enriched["_ew_important_low"] = low.rolling(window, min_periods=1).min()
    else:
        enriched["_ew_important_high"] = high.rolling(
            cfg.important_lookback, min_periods=1
        ).max()
        enriched["_ew_important_low"] = low.rolling(
            cfg.important_lookback, min_periods=1
        ).min()
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
                )
            )

    pivots.sort(key=lambda item: (item.position, -item.kind))
    return pivots


def _build_swings(pivots: list[_Swing], cfg: ElliottWaveConfig) -> list[_Swing]:
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
        elif _passes_swing_filter(pivot, last, cfg):
            swings.append(pivot)

        if len(swings) > cfg.max_swings:
            swings = swings[-cfg.max_swings:]

    return swings


def _passes_swing_filter(pivot: _Swing, last: _Swing, cfg: ElliottWaveConfig) -> bool:
    distance = abs(pivot.price - last.price)
    min_by_atr = pivot.atr * cfg.min_swing_atr_multiple if np.isfinite(pivot.atr) else 0.0
    min_by_range = pivot.important_range * cfg.min_swing_range_pct if np.isfinite(pivot.important_range) else 0.0
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

    lifecycle = _run_candidate_state(swings, cfg, source)
    for event in lifecycle["events"]:
        event_index = event["index"]
        if event_index not in result.index:
            continue
        for column, value in event["values"].items():
            result.loc[event_index, column] = value

    active = lifecycle["active"]
    if active is not None:
        base = swings[active["start_idx"]]
        direction = "bullish" if active["bullish"] else "bearish"
        degree_name, degree_timeframe = _degree_metadata(cfg)
        common = {
            "ew_pivot": True,
            "ew_cycle": lifecycle["recount_count"],
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
            "ew_w1_degree_progress": active["degree_progress"],
            "ew_internal_count": active["internal_count"],
            "ew_recount_count": lifecycle["recount_count"],
            "ew_alternate_bases": lifecycle["alternate_count"],
            "ew_parent_state": active["parent_state"],
            "ew_time_rule_mode": cfg.time_rule_mode,
        }
        for fib_ratio, fib_name in _FIB_LEVELS:
            common[f"ew_anchor_fib_{fib_name}"] = _anchor_fib_price(base, fib_ratio)

        phase_by_label = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "A": 6, "B": 7, "C": 8}
        for label, wave in active["waves"].items():
            phase = phase_by_label[label]
            swing = swings[int(wave["swing_idx"])]
            for column, value in common.items():
                result.loc[swing.index, column] = value
            result.loc[swing.index, "ew_confirmed_at"] = swing.confirmed_index
            result.loc[swing.index, "ew_phase"] = phase
            result.loc[swing.index, "ew_label"] = label
            result.loc[swing.index, "ew_candidate_label"] = label
            result.loc[swing.index, "ew_pattern"] = wave["pattern"]
            result.loc[swing.index, "ew_subtype"] = wave["subtype"]
            result.loc[swing.index, "ew_reason_code"] = wave["reason_code"]
            result.loc[swing.index, "ew_source_rule_id"] = wave["source_rule_id"]
            result.loc[swing.index, "ew_rule_note"] = wave["note"]
            result.loc[swing.index, "ew_next_condition"] = active["next_condition"]
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

    result.attrs["elliott_wave_state"] = {
        "engine": "Candidate State",
        "phase": "V4.0 motive and larger-correction sequence",
        "state": active["parent_state"] if active is not None else lifecycle["final_state"],
        "base_locked": active is not None,
        "confirmed_labels": list(active["waves"].keys()) if active is not None else [],
        "recount_count": lifecycle["recount_count"],
        "alternate_base_count": lifecycle["alternate_count"],
        "last_reason_code": lifecycle["last_reason_code"],
        "pending_modules": [
            "double/triple and triangle correction families",
            "full diagonal classifier",
            "full multi-degree routing",
            "owner-blocked conflict decisions",
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


def _run_candidate_state(
    swings: list[_Swing],
    cfg: ElliottWaveConfig,
    source: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Return deterministic state transitions for the core impulse engine."""

    events: list[dict[str, object]] = []
    active: dict[str, object] | None = None
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
                        "values": {
                            "ew_engine_state": "INVALID",
                            "ew_rule_state": "invalid",
                            "ew_rule_note": "Hard invalidation: price crossed locked Point 0.",
                            "ew_reason_code": last_reason_code,
                            "ew_recount_reason": last_reason_code,
                            "ew_next_condition": "Release the count and search for a new qualified base.",
                            "ew_recount_count": recount_count,
                            "ew_base_locked": False,
                        },
                    }
                )
                search_floor = break_position
                active = None

        processed.append(swing_index)
        if active is None:
            candidate = _candidate_ending_at(
                swings, processed, swing_index, search_floor, cfg, source
            )
            if candidate is not None:
                active = candidate
                active.update(
                    {
                        "last_checked_position": swing.confirmed_position,
                        "parent_state": "W2_CORRECTION_CONTAINER",
                        "next_condition": "Need a valid W2 correction completion while Point 0 remains intact.",
                        "waves": {
                            "0": _make_wave_record(
                                swing_idx=int(candidate["start_idx"]),
                                pattern="Base",
                                subtype="LOCKED_BASE",
                                reason_code="BASE_LOCKED",
                                source_rule_id="V3-P2-BASE",
                                note="Qualified Important H/L base locked after Wave 1 degree confirmation.",
                            ),
                            "1": _make_wave_record(
                                swing_idx=int(candidate["end_idx"]),
                                pattern="Motive",
                                subtype=(
                                    "EXTENDED_W1"
                                    if int(candidate["internal_count"]) > 5
                                    else "NORMAL_W1"
                                ),
                                reason_code="W1_CONFIRMED",
                                source_rule_id="V3-P24-W1",
                                note=str(candidate["note"]),
                                fib_anchor="Important H/L",
                                fib_value=float(candidate["degree_progress"]),
                                internal_pattern="5/9/13/17/21-move impulse",
                                internal_count=int(candidate["internal_count"]),
                            ),
                        },
                    }
                )
                last_reason_code = "W1_CONFIRMED"
                events.append(
                    {
                        "index": swing.index,
                        "values": {
                            "ew_engine_state": "CONFIRMED",
                            "ew_candidate_label": "1",
                            "ew_pattern": "Motive",
                            "ew_subtype": active["waves"]["1"]["subtype"],
                            "ew_reason_code": last_reason_code,
                            "ew_rule_state": "ok",
                            "ew_rule_note": candidate["note"],
                            "ew_next_condition": active["next_condition"],
                            "ew_parent_state": active["parent_state"],
                            "ew_source_rule_id": "V3-P24-W1",
                            "ew_base_locked": True,
                            "ew_base_price": candidate["base_price"],
                            "ew_base_position": candidate["base_position"],
                            "ew_w1_degree_progress": candidate["degree_progress"],
                            "ew_internal_count": candidate["internal_count"],
                            "ew_recount_count": recount_count,
                        },
                    }
                )
            else:
                events.append(
                    {
                        "index": swing.index,
                        "values": {
                            "ew_engine_state": "SEARCHING",
                            "ew_reason_code": "SEARCHING_FOR_BASE",
                            "ew_next_condition": "Wait for a qualified base and a 5/9/13/17/21-move Wave 1 candidate.",
                            "ew_recount_count": recount_count,
                        },
                    }
                )
        else:
            active["last_checked_position"] = swing.confirmed_position
            if swing_index != active["end_idx"]:
                base = swings[int(active["start_idx"])]
                same_as_base = swing.kind == base.kind
                alternate = bool(
                    same_as_base
                    and swing.important_extreme
                    and _oscillator_evidence(swings, swing_index, active["bullish"], cfg)[0]
                )
                transition = _advance_impulse_state(active, swings, swing_index, cfg)
                if alternate and transition["status"] != "CONFIRMED":
                    alternate_count += 1
                    transition["alternate_pattern"] = "Alternate base"
                    if not transition["candidate_label"]:
                        transition["candidate_label"] = "Alt 0"
                last_reason_code = str(transition["reason_code"])
                events.append(
                    {
                        "index": swing.index,
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
                            "ew_base_locked": True,
                            "ew_base_price": base.price,
                            "ew_base_position": base.position,
                            "ew_recount_count": recount_count,
                            "ew_alternate_bases": alternate_count,
                        },
                    }
                )

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
                    "values": {
                        "ew_engine_state": "INVALID",
                        "ew_rule_state": "invalid",
                        "ew_rule_note": "Hard invalidation: price crossed locked Point 0.",
                        "ew_reason_code": last_reason_code,
                        "ew_recount_reason": last_reason_code,
                        "ew_next_condition": "Release the count and search for a new qualified base.",
                        "ew_recount_count": recount_count,
                        "ew_base_locked": False,
                    },
                }
            )
            active = None

    return {
        "active": active,
        "events": events,
        "recount_count": recount_count,
        "alternate_count": alternate_count,
        "final_state": "SEARCHING" if active is None else str(active["parent_state"]),
        "last_reason_code": last_reason_code,
    }


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
    }


def _origin_protection_active(parent_state: str) -> bool:
    """Point 0 is a hard invalidation only while the motive count is forming."""

    return parent_state in {
        "W2_CORRECTION_CONTAINER",
        "W3_FORMING",
        "W4_CORRECTION_CONTAINER",
        "W5_FORMING",
    }


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
) -> dict[str, object]:
    return locals()


def _advance_impulse_state(
    active: dict[str, object],
    swings: list[_Swing],
    end_idx: int,
    cfg: ElliottWaveConfig,
) -> dict[str, object]:
    state = str(active["parent_state"])
    bullish = bool(active["bullish"])
    waves = active["waves"]

    if state == "W2_CORRECTION_CONTAINER":
        start_idx = int(waves["1"]["swing_idx"])
        correction = _evaluate_simple_correction(swings, start_idx, end_idx, cfg)
        p0 = swings[int(waves["0"]["swing_idx"])]
        p1 = swings[start_idx]
        p2 = swings[end_idx]
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
        subtype = "W2_MICROSCOPIC" if microscopic else "W2_NORMAL" if normal else "W2_OUTSIDE_NORMAL"
        hp_signal = (
            "HP BUY ELIGIBLE" if bullish else "HP SELL ELIGIBLE"
        ) if deep and correction["confirmed"] and time_gate and cfg.hp_signal_mode != "Disabled" else ""

        if correct_side and correction["confirmed"] and (normal or microscopic) and time_gate:
            record = _make_wave_record(
                swing_idx=end_idx,
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
            )

        reason = (
            "W2_TIME_GATE_FAIL"
            if correction["confirmed"] and (normal or microscopic) and not time_gate
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
        correction = _evaluate_simple_correction(
            swings, int(waves["3"]["swing_idx"]), end_idx, cfg
        )
        correct_side = p4.kind == (-1 if bullish else 1)
        retrace = _safe_ratio(abs(p3.price - p4.price), abs(p3.price - p0.price))
        w3_terminal = "TERMINAL" in str(waves["3"]["subtype"])
        max_retrace = cfg.wave4_terminal_max_retrace if w3_terminal else cfg.wave4_max_retrace
        price_pass = _w4_minimum(cfg) <= retrace <= max_retrace
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
        if correction["confirmed"] and correct_side and price_pass:
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
            record = _make_wave_record(
                swing_idx=end_idx,
                pattern=str(correction["primary"]),
                subtype="W4_NORMAL" if not w3_terminal else "W4_TERMINAL_CONTEXT",
                reason_code="W4_CONFIRMED",
                source_rule_id="V3-P26-W4",
                note=(
                    f"Wave 4 {correction['primary']} completed; Base-P3 retracement={retrace:.2%}; "
                    f"W2/W4 similarity difference={similarity:.2%}."
                ),
                fib_anchor="Base-P3 retracement",
                fib_value=retrace,
                time_value=time_ratio,
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
                alternate=str(correction["alternate"]),
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
                source_rule_id="V3-P26-W4",
                alternate_pattern=str(correction["alternate"]),
                fib_anchor="Base-P3 retracement",
                fib_value=retrace,
                time_value=time_ratio,
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
            )
        return _transition(
            candidate_label="4?" if correct_side else "",
            pattern=str(correction["primary"]),
            subtype="W4_CORRECTION_CONTAINER",
            reason_code=(
                "W4_RETRACE_OUTSIDE_NORMAL" if correction["confirmed"] else str(correction["reason_code"])
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
        internal_valid = internal_count in cfg.w1_internal_move_counts and correct_side
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
        divergence_pass = cfg.wave5_divergence_mode != "Required" or divergence
        normal = cfg.wave5_min_extension <= ratio <= cfg.wave5_max_extension
        double_extension = (
            float(waves["1"]["internal_count"]) > 5
            and float(waves["3"]["internal_count"]) > 5
        )
        truncated = double_extension and ratio <= 0.812
        if internal_valid and not w3_shortest and divergence_pass and (normal or truncated):
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
                    pattern="Motive",
                    subtype="W5_TIME_PENDING",
                    reason_code="W5_TIME_GATE_FAIL",
                    note=f"Wave 5 structure passes but duration {w5_duration} misses the V4 time windows.",
                    next_condition="Wait for a permitted W5 time window; the completed W4 remains locked.",
                    source_rule_id="V4-C09-W5-TIME",
                    fib_anchor="P3-P4 projection",
                    fib_value=ratio,
                    macd_state="W3/W5 DIVERGENCE PASS" if divergence else "W3/W5 DIVERGENCE ABSENT",
                    internal_pattern="5/9/13/17/21-move impulse",
                    internal_count=internal_count,
                )
            subtype = "W5_TRUNCATED" if truncated else "W5_NORMAL"
            macd_state = "W3/W5 DIVERGENCE PASS" if divergence else "W3/W5 DIVERGENCE ABSENT"
            time_ratio = _duration_ratio(p4, p5, p0, p1)
            record = _make_wave_record(
                swing_idx=end_idx,
                pattern="Motive",
                subtype=subtype,
                reason_code="W5_CONFIRMED",
                source_rule_id="V3-P26-27-W5",
                note=f"{subtype} confirmed; 3-4 projection={ratio:.2%}; W3 shortest=false.",
                fib_anchor="P3-P4 projection",
                fib_value=ratio,
                time_value=time_ratio,
                macd_state=macd_state,
                internal_pattern="5/9/13/17/21-move impulse",
                internal_count=internal_count,
            )
            waves["5"] = record
            active["parent_state"] = "LARGER_CORRECTION_CONTAINER"
            active["next_condition"] = "Five-wave impulse locked; classify the larger correction in parallel."
            return _transition(
                status="CONFIRMED",
                candidate_label="5",
                pattern="Motive",
                subtype=subtype,
                reason_code="W5_CONFIRMED",
                note=str(record["note"]),
                next_condition=active["next_condition"],
                source_rule_id="V3-P26-27-W5",
                fib_anchor="P3-P4 projection",
                fib_value=ratio,
                time_value=time_ratio,
                macd_state=macd_state,
                internal_pattern="5/9/13/17/21-move impulse",
                internal_count=internal_count,
            )
        reason = "W5_W3_SHORTEST" if w3_shortest else "W5_INTERNAL_FAIL" if not internal_valid else "W5_PRICE_SUBTYPE_PENDING"
        return _transition(
            status="INVALID" if w3_shortest else "FORMING",
            candidate_label="5?" if correct_side else "",
            pattern="Motive",
            subtype="W5_EXTENSION_TBD" if ratio > cfg.wave5_max_extension else "W5_CANDIDATE",
            reason_code=reason,
            note=f"Wave 5 forming: 3-4 projection={ratio:.2%}, internal moves={internal_count}.",
            next_condition="Need a valid normal/truncated/extended/ED subtype and deferred W3-shortest check.",
            source_rule_id="V3-P26-27-W5",
            fib_anchor="P3-P4 projection",
            fib_value=ratio,
            macd_state="W3/W5 DIVERGENCE PASS" if divergence else "W3/W5 DIVERGENCE ABSENT",
            internal_pattern="Impulse candidate",
            internal_count=internal_count,
        )

    if state == "LARGER_CORRECTION_CONTAINER":
        start_idx = int(waves["5"]["swing_idx"])
        correction = _evaluate_simple_correction(swings, start_idx, end_idx, cfg)
        terminal = swings[end_idx]
        correct_side = terminal.kind == (-1 if bullish else 1)
        if correction["confirmed"] and correct_side:
            endpoint_indices = correction["endpoint_indices"]
            for label, endpoint_idx in zip(("A", "B", "C"), endpoint_indices):
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
                    fib_value=(
                        float(correction["b_ratio"])
                        if label == "B"
                        else float(correction["c_vs_a"])
                        if label == "C"
                        else np.nan
                    ),
                    internal_pattern=str(correction["internal_pattern"]),
                    internal_count=int(correction[f"{label.lower()}_count"]),
                    alternate=str(correction["alternate"]),
                )
            active["parent_state"] = "CORRECTION_CONFIRMED"
            active["next_condition"] = "The 1-2-3-4-5 then A-B-C cycle is complete; wait for the next qualified Point 0."
            return _transition(
                status="CONFIRMED",
                candidate_label="C",
                pattern=str(correction["primary"]),
                subtype="LARGER_CORRECTION_COMPLETE",
                reason_code="CORRECTION_COMPLETE",
                note=(
                    f"Larger {correction['primary']} completed as "
                    f"{correction['internal_pattern']}; A-B-C labels locked on actual pivots."
                ),
                next_condition=active["next_condition"],
                source_rule_id="V4-C10-C16-LARGER-CORRECTION",
                alternate_pattern=str(correction["alternate"]),
                fib_anchor="Wave 5 correction origin",
                fib_value=float(correction["c_vs_a"]),
                internal_pattern=str(correction["internal_pattern"]),
                internal_count=int(correction["internal_count"]),
            )

        candidate_label = _larger_correction_candidate_label(
            end_idx - start_idx, cfg
        )
        return _transition(
            candidate_label=candidate_label,
            pattern=str(correction["primary"]),
            subtype="LARGER_CORRECTION_CONTAINER",
            reason_code=str(correction["reason_code"]),
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


def _evaluate_simple_correction(
    swings: list[_Swing], start_idx: int, end_idx: int, cfg: ElliottWaveConfig
) -> dict[str, object]:
    """Evaluate source-locked Zig-Zag and Flat candidates in parallel."""

    candidates: list[dict[str, object]] = []
    impulse_counts = cfg.w1_internal_move_counts
    correction_counts = (3, 7, 11)

    for a_count in impulse_counts:
        for b_count in correction_counts:
            for c_count in impulse_counts:
                if start_idx + a_count + b_count + c_count != end_idx:
                    continue
                candidate = _correction_ratios(
                    swings, start_idx, a_count, b_count, c_count
                )
                if (
                    0.01 <= candidate["b_ratio"] <= 0.618
                    and 0.618 <= candidate["c_vs_a"] <= 4.618
                ):
                    candidates.append(
                        {
                            **candidate,
                            "pattern": "Zig-Zag",
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
            for c_count in impulse_counts:
                if start_idx + a_count + b_count + c_count != end_idx:
                    continue
                candidate = _correction_ratios(
                    swings, start_idx, a_count, b_count, c_count
                )
                if (
                    cfg.flat_b_min_retrace <= candidate["b_ratio"] <= cfg.flat_b_max_retrace
                    and 0.618 <= candidate["c_vs_a"] <= 2.618
                ):
                    candidates.append(
                        {
                            **candidate,
                            "pattern": "Flat",
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
        primary = candidates[0]
        alternate = candidates[1]["pattern"] if len(candidates) > 1 else ""
        return {
            "confirmed": True,
            "primary": primary["pattern"],
            "alternate": alternate,
            "b_ratio": primary["b_ratio"],
            "c_vs_a": primary["c_vs_a"],
            "c_vs_b": primary["c_vs_b"],
            "a_count": primary["a_count"],
            "b_count": primary["b_count"],
            "c_count": primary["c_count"],
            "endpoint_indices": primary["endpoint_indices"],
            "internal_pattern": primary["internal_pattern"],
            "internal_count": end_idx - start_idx,
            "reason_code": "CORRECTION_CONFIRMED",
            "note": (
                f"{primary['pattern']} {primary['internal_pattern']} passes; "
                f"B={primary['b_ratio']:.2%}, C/A={primary['c_vs_a']:.2%}."
            ),
        }

    b_ratio = np.nan
    if end_idx - start_idx >= 6:
        a = swings[start_idx + 3]
        b = swings[start_idx + 6]
        b_ratio = _safe_ratio(abs(b.price - a.price), abs(a.price - swings[start_idx].price))
    reason = "FLAT_B_GT_111" if np.isfinite(b_ratio) and b_ratio > cfg.flat_b_max_retrace else "C_INTERNAL_INCOMPLETE"
    return {
        "confirmed": False,
        "primary": "Zig-Zag / Flat",
        "alternate": "",
        "b_ratio": b_ratio,
        "c_vs_a": np.nan,
        "c_vs_b": np.nan,
        "a_count": 0,
        "b_count": 0,
        "c_count": 0,
        "endpoint_indices": (),
        "internal_pattern": "parallel candidates",
        "internal_count": max(0, end_idx - start_idx),
        "reason_code": reason,
        "note": "Parallel Zig-Zag and Flat candidates remain forming; required internal counts/Fib gates are incomplete.",
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


def _candidate_ending_at(
    swings: list[_Swing],
    processed_indices: list[int],
    end_idx: int,
    search_floor: int,
    cfg: ElliottWaveConfig,
    source: pd.DataFrame | None,
) -> dict[str, object] | None:
    processed_set = set(processed_indices)
    for internal_count in cfg.w1_internal_move_counts:
        start_idx = end_idx - internal_count
        if start_idx < 0 or start_idx not in processed_set:
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

        distance = abs(end.price - start.price)
        degree_progress = _safe_ratio(distance, start.important_range)
        degree_ok = np.isfinite(degree_progress) and degree_progress >= cfg.degree_retrace
        important_ok = cfg.wave1_start_mode == "Off" or start.important_extreme
        atr_ok = cfg.important_atr_multiple <= 0 or (
            np.isfinite(start.atr) and distance >= start.atr * cfg.important_atr_multiple
        )
        oscillator_ok, oscillator_note = _oscillator_evidence(
            swings, start_idx, bullish, cfg
        )
        if cfg.wave1_start_mode == "Important swing":
            oscillator_ok = True
        if not (degree_ok and important_ok and atr_ok and oscillator_ok):
            continue
        if _candidate_crosses_origin(
            swings, start_idx, end_idx, bullish, source, end.confirmed_position
        ):
            continue

        return {
            "start_idx": start_idx,
            "end_idx": end_idx,
            "bullish": bullish,
            "base_price": start.price,
            "base_position": start.position,
            "degree_progress": degree_progress,
            "internal_count": internal_count,
            "note": (
                f"Wave 1 confirmed with {internal_count} internal moves and "
                f"{degree_progress:.2%} degree progress; {oscillator_note}."
            ),
        }
    return None


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
    if cfg.correction_pattern in {"W-X-Y-X-Z", "A-B-C-D-E"}:
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
        "W-X-Y-X-Z": {0: "W", 1: "X", 2: "Y", 3: "X", 4: "Z"},
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
