"""State-based Elliott Wave overlay engine.

The confirmed pivot/ATR layer is only a raw market-structure provider.  Main
Elliott labels are emitted by a persistent candidate lifecycle so that a new
minor pivot cannot advance or restart the main-degree count by itself.

Phase 1 implements the P0 foundation from the developer manual: raw/main pivot
separation, degree-aware Important High/Low context, Point-0 candidates,
persistent base locking, W1 degree confirmation, hard origin invalidation and
controlled recount audit fields.  Later impulse/correction classifiers remain
explicitly visible as pending rather than being simulated with modulo labels.
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
    max_swings: int = 45
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
    rsi_length: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    oscillator_lookback: int = 100
    important_lookback: int = 144
    degree_retrace: float = 0.618
    wave2_min_retrace: float = 0.14
    wave2_max_time: float = 2.0
    wave3_min_extension: float = 1.618
    wave4_min_retrace: float = 0.14
    wave4_max_retrace: float = 0.50
    flat_a_max_retrace: float = 0.618
    flat_b_min_retrace: float = 0.618
    flat_b_max_retrace: float = 1.11
    wave5_min_extension: float = 1.27
    wave5_max_extension: float = 2.618
    time_tolerance: float = 0.25
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
    if cfg.flat_b_max_retrace < cfg.flat_b_min_retrace:
        raise ValueError("flat_b_max_retrace must be greater than or equal to flat_b_min_retrace")


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
    """Apply the Phase-1 candidate lifecycle without inventing later waves."""

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
        wave1 = swings[active["end_idx"]]
        direction = "bullish" if active["bullish"] else "bearish"
        degree_name, degree_timeframe = _degree_metadata(cfg)
        common = {
            "ew_pivot": True,
            "ew_confirmed_at": wave1.confirmed_index,
            "ew_cycle": lifecycle["recount_count"],
            "ew_correction_pattern": "TBD - correction classifier not active in Phase 1",
            "ew_rule_state": "ok",
            "ew_start_confirmed": True,
            "ew_anchor_direction": direction,
            "ew_anchor_important_high": base.important_high,
            "ew_anchor_important_low": base.important_low,
            "ew_engine_state": "CONFIRMED",
            "ew_pattern": "Motive candidate",
            "ew_subtype": "TBD",
            "ew_reason_code": "W1_CONFIRMED",
            "ew_degree": degree_name,
            "ew_degree_timeframe": degree_timeframe,
            "ew_base_locked": True,
            "ew_base_price": base.price,
            "ew_base_position": base.position,
            "ew_w1_degree_progress": active["degree_progress"],
            "ew_internal_count": active["internal_count"],
            "ew_recount_count": lifecycle["recount_count"],
            "ew_alternate_bases": lifecycle["alternate_count"],
        }
        for fib_ratio, fib_name in _FIB_LEVELS:
            common[f"ew_anchor_fib_{fib_name}"] = _anchor_fib_price(base, fib_ratio)

        for phase, swing, label in ((0, base, "0"), (1, wave1, "1")):
            for column, value in common.items():
                result.loc[swing.index, column] = value
            result.loc[swing.index, "ew_phase"] = phase
            result.loc[swing.index, "ew_label"] = label
            result.loc[swing.index, "ew_candidate_label"] = label
            result.loc[swing.index, "ew_rule_note"] = active["note"]
            result.loc[swing.index, "ew_next_condition"] = (
                "Protect Point 0 and wait for the Wave 2 correction classifiers."
            )

    result.attrs["elliott_wave_state"] = {
        "engine": "Candidate State",
        "phase": "Phase 1 / P0 foundation",
        "state": "CONFIRMED" if active is not None else lifecycle["final_state"],
        "base_locked": active is not None,
        "recount_count": lifecycle["recount_count"],
        "alternate_base_count": lifecycle["alternate_count"],
        "last_reason_code": lifecycle["last_reason_code"],
        "pending_modules": [
            "Wave 2-5 classifiers",
            "automatic correction family detection",
            "diagonal classifier",
            "full multi-degree routing",
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
    """Return deterministic state transitions for the Phase-1 engine.

    The function is intentionally independent from chart drawing so the hard
    lifecycle rules can be regression-tested with synthetic confirmed pivots.
    """

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
        if active is not None:
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
                active["last_checked_position"] = swing.confirmed_position
                last_reason_code = "W1_CONFIRMED"
                events.append(
                    {
                        "index": swing.index,
                        "values": {
                            "ew_engine_state": "CONFIRMED",
                            "ew_candidate_label": "1",
                            "ew_pattern": "Motive candidate",
                            "ew_subtype": "TBD",
                            "ew_reason_code": last_reason_code,
                            "ew_rule_state": "ok",
                            "ew_rule_note": candidate["note"],
                            "ew_next_condition": "Protect Point 0; classify Wave 2 when its module is enabled.",
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
                if alternate:
                    alternate_count += 1
                    state = "ALTERNATE"
                    candidate_label = "Alt 0"
                    reason = "LOCKED_BASE_ALTERNATE"
                    note = "A new important same-side pivot is stored as an alternate; the locked base is unchanged."
                else:
                    state = "FORMING"
                    candidate_label = "2?" if same_as_base else ""
                    reason = "W2_CLASSIFIER_PENDING"
                    note = "The raw pivot is retained, but Phase 1 does not promote it to a main Elliott label."
                events.append(
                    {
                        "index": swing.index,
                        "values": {
                            "ew_engine_state": state,
                            "ew_candidate_label": candidate_label,
                            "ew_pattern": "TBD",
                            "ew_subtype": "TBD",
                            "ew_reason_code": reason,
                            "ew_rule_state": "pending",
                            "ew_rule_note": note,
                            "ew_next_condition": "Run the Wave 2 and correction-family classifiers in Phase 2.",
                            "ew_base_locked": True,
                            "ew_base_price": base.price,
                            "ew_base_position": base.position,
                            "ew_recount_count": recount_count,
                            "ew_alternate_bases": alternate_count,
                        },
                    }
                )

    if active is not None and source is not None:
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
        "final_state": "SEARCHING" if active is None else "CONFIRMED",
        "last_reason_code": last_reason_code,
    }


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
        time_warning = abs(time_ratio - 1.0) > cfg.time_tolerance
        warning = ratio < cfg.wave3_min_extension or time_warning
        return _state(False, warning), (
            f"Wave 3={ratio:.2%} of Wave 1, time={time3} bars vs rule {expected3:.2f}"
        ), None, duration, time_ratio

    if cfg.show_wave4_internal and phase == 4 and wave_index >= 4:
        p2 = swings[cycle_start + 2].price
        p3 = swings[cycle_start + 3].price
        p_a = swings[cycle_start + 4].price
        retrace = _safe_ratio(abs(p3 - p_a), abs(p3 - p2))
        warning = retrace > cfg.flat_a_max_retrace
        return _state(False, warning), (
            f"Wave 4 A retrace={retrace:.2%} of W3, flat max={cfg.flat_a_max_retrace:.2%}"
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
        time_warning = not _near_any(time_ratio, (0.5, 2.0, 3.0), cfg.time_tolerance)
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
