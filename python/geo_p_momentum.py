"""GEO P Momentum signal engine.

This module mirrors ``pine/geo_p_momentum_strategy.pine`` for the first client
setup: Momentum Trader: Bollinger Band Challenge with Trendline Break.

Input data must contain open, high, low, close, and volume columns. A
DatetimeIndex is recommended when using a separate higher-timeframe tide filter.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GeoPMomentumConfig:
    """Configurable parameters shared with the Pine Script version."""

    tide_timeframe: str | None = None
    signal_mode: str = "Balanced"
    ti_fast: int = 13
    ti_slow: int = 26
    bb_length: int = 20
    bb_mult: float = 2.0
    rsi_length: int = 14
    rsi_long_base: float = 50.0
    rsi_short_base: float = 50.0
    rsi_strong_long: float = 60.0
    rsi_strong_short: float = 40.0
    volume_length: int = 20
    pivot_left: int = 5
    pivot_right: int = 5
    trend_fallback_lookback: int = 20
    band_trend_sync_bars: int = 3
    ema_cross_lookback: int = 3
    dmi_length: int = 14
    adx_smoothing: int = 14
    adx_floor: float = 15.0
    min_signal_confirmations: int | None = None
    min_better_confirmations: int = 0
    atr_length: int = 14
    stop_atr_buffer: float = 0.0
    major_sr_lookback: int = 100
    major_sr_min_atr: float = 1.0
    target_lookback: int = 80
    fib_target_1: float = 0.618
    fib_target_2: float = 1.0
    fib_target_3: float = 1.618


OHLCV = ("open", "high", "low", "close", "volume")


def compute_signals(
    candles: pd.DataFrame,
    config: GeoPMomentumConfig | None = None,
    tide_candles: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return indicator columns, buy/sell signals, stops, and targets.

    ``tide_candles`` can be supplied as pre-aggregated higher-timeframe OHLCV.
    If omitted and ``config.tide_timeframe`` is set, the module resamples
    ``candles`` with pandas. For exact TradingView parity, use the same market
    sessions and bar close timestamps that TradingView uses.
    """

    cfg = config or GeoPMomentumConfig()
    wave_source = _normalize_ohlcv(candles)
    wave = _frame_indicators(wave_source, cfg)

    if tide_candles is not None:
        tide_source = _normalize_ohlcv(tide_candles)
        tide = _frame_indicators(tide_source, cfg).reindex(wave.index, method="ffill")
    elif cfg.tide_timeframe:
        tide_source = _resample_ohlcv(wave_source, cfg.tide_timeframe)
        tide = _frame_indicators(tide_source, cfg).reindex(wave.index, method="ffill")
    else:
        tide = wave

    result = wave_source.copy()
    result = result.join(wave.add_prefix("wave_"))
    result = result.join(tide.add_prefix("tide_"))

    # Tide timeframe gates define the broader setup direction.
    result["tide_bbuc"] = result["tide_high"] >= result["tide_bb_upper"]
    result["tide_bbdc"] = result["tide_low"] <= result["tide_bb_lower"]
    result["tide_upper_half"] = result["tide_close"] >= result["tide_bb_basis"]
    result["tide_lower_half"] = result["tide_close"] <= result["tide_bb_basis"]
    result["tide_long_bias"] = result["tide_bbuc"] | result["tide_upper_half"]
    result["tide_short_bias"] = result["tide_bbdc"] | result["tide_lower_half"]
    result["tide_ti_above_zero"] = result["tide_ti"] > 0
    result["tide_ti_below_zero"] = result["tide_ti"] < 0

    # RSI is checked on both Tide and Wave, matching the PDF wording.
    result["rsi_long_base_ok"] = (
        (result["tide_rsi"] > cfg.rsi_long_base)
        & (result["wave_rsi"] > cfg.rsi_long_base)
    )
    result["rsi_short_base_ok"] = (
        (result["tide_rsi"] < cfg.rsi_short_base)
        & (result["wave_rsi"] < cfg.rsi_short_base)
    )
    result["rsi_strong_long_cross"] = _crossover(
        result["wave_rsi"], pd.Series(cfg.rsi_strong_long, index=result.index)
    )
    result["rsi_strong_short_cross"] = _crossunder(
        result["wave_rsi"], pd.Series(cfg.rsi_strong_short, index=result.index)
    )

    # Wave requires the Bollinger challenge and trendline break to occur close together.
    result["wave_bbu_with_tlbo"] = _recent(
        result["wave_bbuc"], cfg.band_trend_sync_bars
    ) & _recent(result["wave_tlbo"], cfg.band_trend_sync_bars)
    result["wave_bbd_with_tlbd"] = _recent(
        result["wave_bbdc"], cfg.band_trend_sync_bars
    ) & _recent(result["wave_tlbd"], cfg.band_trend_sync_bars)
    result["volume_long_ok"] = (
        (result["close"] > result["open"]) & (result["volume"] > result["wave_vol_avg"])
    )
    result["volume_short_ok"] = (
        (result["close"] < result["open"]) & (result["volume"] > result["wave_vol_avg"])
    )

    ema_pos_cross = _crossover(result["wave_ema5"], result["wave_ema13"]) | _crossover(
        result["wave_ema5"], result["wave_ema26"]
    )
    ema_neg_cross = _crossunder(result["wave_ema5"], result["wave_ema13"]) | _crossunder(
        result["wave_ema5"], result["wave_ema26"]
    )
    result["ema_pos_cross_recent"] = _recent(ema_pos_cross, cfg.ema_cross_lookback)
    result["ema_neg_cross_recent"] = _recent(ema_neg_cross, cfg.ema_cross_lookback)

    di_pco = _crossover(result["wave_di_plus"], result["wave_di_minus"])
    di_nco = _crossover(result["wave_di_minus"], result["wave_di_plus"])
    result["di_pco"] = _recent(di_pco, cfg.ema_cross_lookback)
    result["di_nco"] = _recent(di_nco, cfg.ema_cross_lookback)
    # ADX Ungli from the chart examples: ADX hooks upward while directional
    # movement separates in the trade direction.
    di_spread = (result["wave_di_plus"] - result["wave_di_minus"]).abs()
    result["di_spread_expanding"] = di_spread > di_spread.shift(1)
    result["adx_hook"] = (result["wave_adx"] > result["wave_adx"].shift(1)) & (
        result["wave_adx"].shift(1) <= result["wave_adx"].shift(2)
    )
    result["adx_ungli_buy"] = (
        result["adx_hook"]
        & (result["wave_di_plus"] > result["wave_di_minus"])
        & result["di_spread_expanding"]
    )
    result["adx_ungli_sell"] = (
        result["adx_hook"]
        & (result["wave_di_minus"] > result["wave_di_plus"])
        & result["di_spread_expanding"]
    )
    result["adx_buy_ok"] = (
        _recent(result["adx_ungli_buy"], cfg.ema_cross_lookback)
        | (result["wave_adx"] >= cfg.adx_floor)
    )
    result["adx_sell_ok"] = (
        _recent(result["adx_ungli_sell"], cfg.ema_cross_lookback)
        | (result["wave_adx"] >= cfg.adx_floor)
    )

    major_resistance = result["high"].rolling(cfg.major_sr_lookback).max().shift(1)
    major_support = result["low"].rolling(cfg.major_sr_lookback).min().shift(1)
    result["major_resistance"] = major_resistance
    result["major_support"] = major_support
    result["no_immediate_resistance"] = (
        major_resistance.isna()
        | (result["close"] >= major_resistance)
        | ((major_resistance - result["close"]) > result["wave_atr"] * cfg.major_sr_min_atr)
    )
    result["no_immediate_support"] = (
        major_support.isna()
        | (result["close"] <= major_support)
        | ((result["close"] - major_support) > result["wave_atr"] * cfg.major_sr_min_atr)
    )

    # Score PDF Buy/Sell rows and separate Better rows so strictness stays configurable.
    result["long_confirmations"] = _count_true(
        result["volume_long_ok"],
        result["wave_two_higher_lows"],
        result["ema_pos_cross_recent"],
        result["di_pco"],
        result["adx_buy_ok"],
    )
    result["short_confirmations"] = _count_true(
        result["volume_short_ok"],
        result["wave_two_lower_highs"],
        result["ema_neg_cross_recent"],
        result["di_nco"],
        result["adx_sell_ok"],
    )
    result["long_better"] = _count_true(
        result["tide_ti_above_zero"],
        result["rsi_strong_long_cross"],
        result["close"] > result["wave_ema50"],
        result["no_immediate_resistance"],
    )
    result["short_better"] = _count_true(
        result["tide_ti_below_zero"],
        result["rsi_strong_short_cross"],
        result["close"] < result["wave_ema50"],
        result["no_immediate_support"],
    )

    result["long_mandatory"] = (
        result["tide_long_bias"]
        & result["tide_ti_up"]
        & result["rsi_long_base_ok"]
        & result["wave_bbu_with_tlbo"]
    )
    result["short_mandatory"] = (
        result["tide_short_bias"]
        & result["tide_ti_down"]
        & result["rsi_short_base_ok"]
        & result["wave_bbd_with_tlbd"]
    )
    required_signal_rows = _required_signal_rows(cfg)

    result["long_setup"] = (
        result["long_mandatory"]
        & (result["long_confirmations"] >= required_signal_rows)
        & (result["long_better"] >= cfg.min_better_confirmations)
    )
    result["short_setup"] = (
        result["short_mandatory"]
        & (result["short_confirmations"] >= required_signal_rows)
        & (result["short_better"] >= cfg.min_better_confirmations)
    )
    result["raw_buy_signal"] = result["long_setup"] & ~result["long_setup"].shift(1).fillna(False)
    result["raw_sell_signal"] = result["short_setup"] & ~result["short_setup"].shift(1).fillna(False)

    swing_range = (
        result["high"].rolling(cfg.target_lookback).max()
        - result["low"].rolling(cfg.target_lookback).min()
    )
    swing_range = pd.concat([swing_range, result["wave_atr"]], axis=1).max(axis=1)
    last_bbu_candle_low = result["low"].where(result["wave_bbuc"]).ffill()
    last_bbd_candle_high = result["high"].where(result["wave_bbdc"]).ffill()
    last_tlbo_point = result["wave_tlbo_point"].where(result["wave_tlbo"]).ffill()
    last_tlbd_point = result["wave_tlbd_point"].where(result["wave_tlbd"]).ffill()

    stop_long_base = pd.concat(
        [last_bbu_candle_low.fillna(result["low"]), last_tlbo_point.fillna(result["low"])],
        axis=1,
    ).min(axis=1)
    stop_short_base = pd.concat(
        [last_bbd_candle_high.fillna(result["high"]), last_tlbd_point.fillna(result["high"])],
        axis=1,
    ).max(axis=1)
    result["long_stop"] = stop_long_base - result["wave_atr"] * cfg.stop_atr_buffer
    result["short_stop"] = stop_short_base + result["wave_atr"] * cfg.stop_atr_buffer

    long_fib_target_1 = result["close"] + swing_range * cfg.fib_target_1
    short_fib_target_1 = result["close"] - swing_range * cfg.fib_target_1
    result["long_target_1"] = major_resistance.where(
        major_resistance > result["close"], long_fib_target_1
    )
    result["long_target_2"] = pd.concat(
        [result["long_target_1"], result["close"] + swing_range * cfg.fib_target_2], axis=1
    ).max(axis=1)
    result["long_target_3"] = pd.concat(
        [result["long_target_2"], result["close"] + swing_range * cfg.fib_target_3], axis=1
    ).max(axis=1)
    result["short_target_1"] = major_support.where(
        major_support < result["close"], short_fib_target_1
    )
    result["short_target_2"] = pd.concat(
        [result["short_target_1"], result["close"] - swing_range * cfg.fib_target_2], axis=1
    ).min(axis=1)
    result["short_target_3"] = pd.concat(
        [result["short_target_2"], result["close"] - swing_range * cfg.fib_target_3], axis=1
    ).min(axis=1)

    long_risk = result["close"] - result["long_stop"]
    short_risk = result["short_stop"] - result["close"]
    result["long_rr_1"] = (result["long_target_1"] - result["close"]) / long_risk
    result["short_rr_1"] = (result["close"] - result["short_target_1"]) / short_risk
    result["buy_signal"] = (
        result["raw_buy_signal"]
        & (result["long_stop"] < result["close"])
        & (result["long_target_1"] > result["close"])
    )
    result["sell_signal"] = (
        result["raw_sell_signal"]
        & (result["short_stop"] > result["close"])
        & (result["short_target_1"] < result["close"])
    )

    return result


def backtest_signals(signals: pd.DataFrame) -> pd.DataFrame:
    """Simple stop/target backtest using target 1.

    If stop and target are both touched in the same candle, the stop is taken
    first. That conservative rule keeps the report deterministic.
    """

    trades: list[dict[str, object]] = []
    position = 0
    entry_time = None
    entry = stop = target = np.nan

    for timestamp, row in signals.iterrows():
        if position == 0:
            if bool(row.get("buy_signal", False)):
                position = 1
                entry_time = timestamp
                entry = float(row["close"])
                stop = float(row["long_stop"])
                target = float(row["long_target_1"])
            elif bool(row.get("sell_signal", False)):
                position = -1
                entry_time = timestamp
                entry = float(row["close"])
                stop = float(row["short_stop"])
                target = float(row["short_target_1"])
            continue

        if position == 1:
            stop_hit = float(row["low"]) <= stop
            target_hit = float(row["high"]) >= target
            opposite = bool(row.get("sell_signal", False))
            if stop_hit or target_hit or opposite:
                exit_price = stop if stop_hit else target if target_hit else float(row["close"])
                reason = "stop" if stop_hit else "target_1" if target_hit else "opposite_signal"
                trades.append(_trade_dict("long", entry_time, timestamp, entry, exit_price, stop, target, reason))
                position = 0
        elif position == -1:
            stop_hit = float(row["high"]) >= stop
            target_hit = float(row["low"]) <= target
            opposite = bool(row.get("buy_signal", False))
            if stop_hit or target_hit or opposite:
                exit_price = stop if stop_hit else target if target_hit else float(row["close"])
                reason = "stop" if stop_hit else "target_1" if target_hit else "opposite_signal"
                trades.append(_trade_dict("short", entry_time, timestamp, entry, exit_price, stop, target, reason))
                position = 0

    return pd.DataFrame(trades)


def _frame_indicators(source: pd.DataFrame, cfg: GeoPMomentumConfig) -> pd.DataFrame:
    out = pd.DataFrame(index=source.index)
    out[OHLCV] = source[list(OHLCV)]

    basis, upper, lower = _bollinger(source["close"], cfg.bb_length, cfg.bb_mult)
    out["bb_basis"] = basis
    out["bb_upper"] = upper
    out["bb_lower"] = lower
    out["bbuc"] = source["high"] >= upper
    out["bbdc"] = source["low"] <= lower
    out["rsi"] = _rsi(source["close"], cfg.rsi_length)
    out["vol_avg"] = source["volume"].rolling(cfg.volume_length).mean()
    out["atr"] = _atr(source["high"], source["low"], source["close"], cfg.atr_length)

    out["ema5"] = _ema(source["close"], 5)
    out["ema13"] = _ema(source["close"], 13)
    out["ema26"] = _ema(source["close"], 26)
    out["ema50"] = _ema(source["close"], 50)
    out["ti"] = _ema(source["close"], cfg.ti_fast) - _ema(source["close"], cfg.ti_slow)
    out["ti_up"] = out["ti"] > out["ti"].shift(1)
    out["ti_down"] = out["ti"] < out["ti"].shift(1)

    plus_di, minus_di, adx = _dmi(
        source["high"], source["low"], source["close"], cfg.dmi_length, cfg.adx_smoothing
    )
    out["di_plus"] = plus_di
    out["di_minus"] = minus_di
    out["adx"] = adx

    pivot_high = _pivot_series(source["high"], cfg.pivot_left, cfg.pivot_right, "high")
    pivot_low = _pivot_series(source["low"], cfg.pivot_left, cfg.pivot_right, "low")
    out["upper_trend"] = _trendline_from_pivots(pivot_high, cfg.pivot_right)
    out["lower_trend"] = _trendline_from_pivots(pivot_low, cfg.pivot_right)

    out["prev_range_high"] = source["high"].rolling(cfg.trend_fallback_lookback).max().shift(1)
    out["prev_range_low"] = source["low"].rolling(cfg.trend_fallback_lookback).min().shift(1)
    pivot_tlbo = _crossover(source["close"], out["upper_trend"])
    pivot_tlbd = _crossunder(source["close"], out["lower_trend"])
    range_tlbo = _crossover(source["close"], out["prev_range_high"])
    range_tlbd = _crossunder(source["close"], out["prev_range_low"])
    out["tlbo_point"] = out["prev_range_high"].where(
        ~(pivot_tlbo & out["upper_trend"].notna()), out["upper_trend"]
    )
    out["tlbd_point"] = out["prev_range_low"].where(
        ~(pivot_tlbd & out["lower_trend"].notna()), out["lower_trend"]
    )
    out["tlbo"] = (pivot_tlbo & out["upper_trend"].notna()) | (
        range_tlbo & out["prev_range_high"].notna()
    )
    out["tlbd"] = (pivot_tlbd & out["lower_trend"].notna()) | (
        range_tlbd & out["prev_range_low"].notna()
    )

    close_pivot_low = _pivot_series(source["close"], cfg.pivot_left, cfg.pivot_right, "low")
    close_pivot_high = _pivot_series(source["close"], cfg.pivot_left, cfg.pivot_right, "high")
    out["two_higher_lows"] = _last_two_pivots_are(close_pivot_low, "rising")
    out["two_lower_highs"] = _last_two_pivots_are(close_pivot_high, "falling")

    return out


def _normalize_ohlcv(candles: pd.DataFrame) -> pd.DataFrame:
    normalized = candles.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    missing = [column for column in OHLCV if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required OHLCV columns: {missing}")
    normalized = normalized.sort_index()
    return normalized


def _resample_ohlcv(candles: pd.DataFrame, rule: str) -> pd.DataFrame:
    if not isinstance(candles.index, pd.DatetimeIndex):
        raise ValueError("A DatetimeIndex is required when resampling tide_timeframe.")
    pandas_rule = _to_pandas_resample_rule(rule)
    return (
        candles.resample(pandas_rule, label="right", closed="right")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
    )


def _to_pandas_resample_rule(timeframe: str) -> str:
    """Accept TradingView-style timeframes for Python parity runs."""

    tf = str(timeframe).strip()
    if not tf:
        raise ValueError("timeframe cannot be blank when resampling.")
    if tf.isdigit():
        return f"{tf}min"

    unit = tf[-1].upper()
    multiplier = tf[:-1] or "1"
    if not multiplier.isdigit():
        return tf
    if unit == "S":
        return f"{multiplier}s"
    if unit == "H":
        return f"{multiplier}h"
    if unit == "D":
        return f"{multiplier}D"
    if unit == "W":
        return f"{multiplier}W"
    if unit == "M":
        return f"{multiplier}ME"
    return tf


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.astype(float).ewm(span=length, adjust=False).mean()


def _rma(series: pd.Series, length: int) -> pd.Series:
    values = series.astype(float).to_numpy()
    out = np.full(len(values), np.nan)
    if len(values) < length:
        return pd.Series(out, index=series.index)

    first_window = values[:length]
    if np.isnan(first_window).any():
        first_valid = pd.Series(values).rolling(length).mean().first_valid_index()
        if first_valid is None:
            return pd.Series(out, index=series.index)
        start = int(first_valid)
        out[start] = np.nanmean(values[start - length + 1 : start + 1])
    else:
        start = length - 1
        out[start] = first_window.mean()

    alpha = 1.0 / length
    for index in range(start + 1, len(values)):
        previous = out[index - 1]
        value = values[index]
        out[index] = previous if np.isnan(value) else (alpha * value) + ((1.0 - alpha) * previous)
    return pd.Series(out, index=series.index)


def _bollinger(series: pd.Series, length: int, multiplier: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    basis = series.rolling(length).mean()
    deviation = series.rolling(length).std(ddof=0) * multiplier
    return basis, basis + deviation, basis - deviation


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    ranges = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    )
    return ranges.max(axis=1)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    return _rma(_true_range(high, low, close), length)


def _rsi(close: pd.Series, length: int) -> pd.Series:
    change = close.diff()
    gain = change.clip(lower=0.0)
    loss = (-change).clip(lower=0.0)
    average_gain = _rma(gain, length)
    average_loss = _rma(loss, length)
    rs = average_gain / average_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100.0)
    rsi = rsi.mask((average_gain == 0) & (average_loss > 0), 0.0)
    return rsi.mask((average_gain == 0) & (average_loss == 0), 50.0)


def _dmi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    di_length: int,
    adx_smoothing: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index
    )
    trur = _rma(_true_range(high, low, close), di_length)
    plus = 100.0 * _rma(plus_dm, di_length) / trur
    minus = 100.0 * _rma(minus_dm, di_length) / trur
    denom = (plus + minus).replace(0.0, np.nan)
    dx = ((plus - minus).abs() / denom).fillna(0.0) * 100.0
    adx = _rma(dx, adx_smoothing)
    return plus, minus, adx


def _pivot_series(series: pd.Series, left: int, right: int, kind: str) -> pd.Series:
    values = series.astype(float).to_numpy()
    pivots = np.full(len(values), np.nan)
    for pivot_index in range(left, len(values) - right):
        window = values[pivot_index - left : pivot_index + right + 1]
        if np.isnan(window).any():
            continue
        candidate = values[pivot_index]
        if kind == "high" and candidate == np.max(window):
            pivots[pivot_index + right] = candidate
        elif kind == "low" and candidate == np.min(window):
            pivots[pivot_index + right] = candidate
    return pd.Series(pivots, index=series.index)


def _trendline_from_pivots(pivots: pd.Series, right: int) -> pd.Series:
    values = pivots.to_numpy()
    trend = np.full(len(values), np.nan)
    last_value = last_position = previous_value = previous_position = None

    for index, value in enumerate(values):
        if not np.isnan(value):
            previous_value = last_value
            previous_position = last_position
            last_value = float(value)
            last_position = index - right

        if (
            last_value is not None
            and previous_value is not None
            and last_position is not None
            and previous_position is not None
            and last_position != previous_position
        ):
            slope = (last_value - previous_value) / (last_position - previous_position)
            trend[index] = previous_value + slope * (index - previous_position)

    return pd.Series(trend, index=pivots.index)


def _last_two_pivots_are(pivots: pd.Series, direction: str) -> pd.Series:
    values = pivots.to_numpy()
    out = np.zeros(len(values), dtype=bool)
    latest = previous = None

    for index, value in enumerate(values):
        if not np.isnan(value):
            previous = latest
            latest = float(value)

        if latest is not None and previous is not None:
            out[index] = latest > previous if direction == "rising" else latest < previous

    return pd.Series(out, index=pivots.index)


def _crossover(left: pd.Series, right: pd.Series) -> pd.Series:
    return (left > right) & (left.shift(1) <= right.shift(1))


def _crossunder(left: pd.Series, right: pd.Series) -> pd.Series:
    return (left < right) & (left.shift(1) >= right.shift(1))


def _recent(condition: pd.Series, bars: int) -> pd.Series:
    return condition.fillna(False).astype(int).rolling(bars + 1, min_periods=1).max().astype(bool)


def _count_true(*conditions: pd.Series) -> pd.Series:
    total = None
    for condition in conditions:
        numeric = condition.fillna(False).astype(int)
        total = numeric if total is None else total + numeric
    if total is None:
        raise ValueError("At least one condition is required.")
    return total


def _required_signal_rows(cfg: GeoPMomentumConfig) -> int:
    if cfg.min_signal_confirmations is not None:
        return cfg.min_signal_confirmations
    if cfg.signal_mode == "Fast":
        return 0
    if cfg.signal_mode == "Balanced":
        return 3
    if cfg.signal_mode == "Strict PDF":
        return 5
    raise ValueError("signal_mode must be one of: Fast, Balanced, Strict PDF")


def _trade_dict(
    side: str,
    entry_time: object,
    exit_time: object,
    entry: float,
    exit_price: float,
    stop: float,
    target: float,
    reason: str,
) -> dict[str, object]:
    pnl = exit_price - entry if side == "long" else entry - exit_price
    risk = entry - stop if side == "long" else stop - entry
    rr = pnl / risk if risk > 0 else np.nan
    return {
        "side": side,
        "entry_time": entry_time,
        "exit_time": exit_time,
        "entry": entry,
        "exit": exit_price,
        "stop": stop,
        "target_1": target,
        "exit_reason": reason,
        "pnl_points": pnl,
        "r_multiple": rr,
    }


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run GEO P Momentum signals on OHLCV CSV data.")
    parser.add_argument("csv", help="Input CSV with open, high, low, close, volume columns.")
    parser.add_argument("--time-column", default=None, help="Optional timestamp column to use as index.")
    parser.add_argument("--tide-timeframe", default=None, help="Optional tide timeframe, for example 60 or 1D.")
    parser.add_argument(
        "--signal-mode",
        default="Balanced",
        choices=["Fast", "Balanced", "Strict PDF"],
        help="Match the TradingView Signal strength input.",
    )
    parser.add_argument(
        "--min-better-confirmations",
        type=int,
        default=0,
        help="Match the TradingView Required Better rows input.",
    )
    parser.add_argument("--output", default=None, help="Optional path for signal CSV output.")
    args = parser.parse_args()

    frame = pd.read_csv(args.csv)
    if args.time_column:
        frame[args.time_column] = pd.to_datetime(frame[args.time_column])
        frame = frame.set_index(args.time_column)

    cfg = GeoPMomentumConfig(
        tide_timeframe=args.tide_timeframe,
        signal_mode=args.signal_mode,
        min_better_confirmations=args.min_better_confirmations,
    )
    signals = compute_signals(frame, cfg)
    trades = backtest_signals(signals)

    if args.output:
        signals.to_csv(args.output)

    buys = int(signals["buy_signal"].sum())
    sells = int(signals["sell_signal"].sum())
    total_pnl = float(trades["pnl_points"].sum()) if not trades.empty else 0.0
    print(f"Buy signals: {buys}")
    print(f"Sell signals: {sells}")
    print(f"Completed trades: {len(trades)}")
    print(f"Total PnL points: {total_pnl:.2f}")


if __name__ == "__main__":
    _main()
