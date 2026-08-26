"""Fake Breakout / Fake Breakdown signal engine.

Mirrors the supplied ``2. FAKE BO BD SETUP.pdf`` checklist.  A signal always
requires a failed break and a following confirmation candle; the remaining
manual rows are scored as probability evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FakeBreakConfig:
    level_lookback: int = 20
    bb_length: int = 20
    bb_mult: float = 2.0
    rsi_length: int = 14
    stochastic_length: int = 14
    stochastic_smooth: int = 3
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    dmi_length: int = 14
    volume_length: int = 20
    target_lookback: int = 80
    min_confirmations: int = 3
    require_band_touch: bool = True


def compute_fake_break_signals(
    candles: pd.DataFrame, config: FakeBreakConfig | None = None
) -> pd.DataFrame:
    """Return FBD buy/FBO sell signals, evidence scores, stops and targets."""
    cfg = config or FakeBreakConfig()
    _validate(candles, cfg)
    out = candles.loc[:, ["open", "high", "low", "close", "volume"]].astype(float).copy()

    close = out["close"]
    high = out["high"]
    low = out["low"]
    open_ = out["open"]
    prev_low = low.rolling(cfg.level_lookback, min_periods=cfg.level_lookback).min().shift(1)
    prev_high = high.rolling(cfg.level_lookback, min_periods=cfg.level_lookback).max().shift(1)

    basis = close.rolling(cfg.bb_length, min_periods=cfg.bb_length).mean()
    dev = close.rolling(cfg.bb_length, min_periods=cfg.bb_length).std(ddof=0) * cfg.bb_mult
    upper, lower = basis + dev, basis - dev
    rsi = _rsi(close, cfg.rsi_length)
    ema_fast = close.ewm(span=cfg.macd_fast, adjust=False).mean()
    ema_slow = close.ewm(span=cfg.macd_slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=cfg.macd_signal, adjust=False).mean()
    ll = low.rolling(cfg.stochastic_length).min()
    hh = high.rolling(cfg.stochastic_length).max()
    stoch_k = (100 * (close - ll) / (hh - ll).replace(0, np.nan)).rolling(cfg.stochastic_smooth).mean()
    stoch_d = stoch_k.rolling(cfg.stochastic_smooth).mean()
    di_plus, di_minus = _dmi(high, low, close, cfg.dmi_length)

    ha_close = (open_ + high + low + close) / 4
    ha_open = (open_.shift(1) + close.shift(1)) / 2
    bull_reversal = (close > open_) & (close >= open_.shift(1)) & (open_ <= close.shift(1))
    bear_reversal = (close < open_) & (open_ >= close.shift(1)) & (close <= open_.shift(1))

    fbd_sweep = (low < prev_low) & (close > prev_low)
    fbo_sweep = (high > prev_high) & (close < prev_high)
    fbd_confirm = fbd_sweep.shift(1, fill_value=False) & (high > high.shift(1)) & (close > high.shift(1))
    fbo_confirm = fbo_sweep.shift(1, fill_value=False) & (low < low.shift(1)) & (close < low.shift(1))

    fbd_evidence = pd.DataFrame({
        "band": low.shift(1) <= lower.shift(1),
        "reversal": bull_reversal,
        "ha": (ha_close > ha_open) & (ha_close.shift(1) <= ha_open.shift(1)),
        "macd": macd > macd.shift(1),
        "rsi": rsi > 40,
        "stoch": _cross(stoch_k, stoch_d),
        "dmi": (di_plus > di_minus) | ((di_plus - di_minus).abs() < (di_plus.shift(1) - di_minus.shift(1)).abs()),
        "volume": out["volume"].shift(1) > out["volume"].rolling(cfg.volume_length).mean().shift(1),
    }).fillna(False)
    fbo_evidence = pd.DataFrame({
        "band": high.shift(1) >= upper.shift(1),
        "reversal": bear_reversal,
        "ha": (ha_close < ha_open) & (ha_close.shift(1) >= ha_open.shift(1)),
        "macd": macd < macd.shift(1),
        "rsi": rsi < 60,
        "stoch": _cross(stoch_d, stoch_k),
        "dmi": (di_minus > di_plus) | ((di_plus - di_minus).abs() < (di_plus.shift(1) - di_minus.shift(1)).abs()),
        "volume": out["volume"].shift(1) > out["volume"].rolling(cfg.volume_length).mean().shift(1),
    }).fillna(False)

    out["previous_low"] = prev_low
    out["previous_high"] = prev_high
    out["fbd_sweep"] = fbd_sweep
    out["fbo_sweep"] = fbo_sweep
    out["fbd_score"] = fbd_evidence.sum(axis=1)
    out["fbo_score"] = fbo_evidence.sum(axis=1)
    band_buy = fbd_evidence["band"] | (not cfg.require_band_touch)
    band_sell = fbo_evidence["band"] | (not cfg.require_band_touch)
    out["fbd_buy"] = fbd_confirm & band_buy & (out["fbd_score"] >= cfg.min_confirmations)
    out["fbo_sell"] = fbo_confirm & band_sell & (out["fbo_score"] >= cfg.min_confirmations)

    out["long_stop"] = np.where(out["fbd_buy"], prev_low.shift(1), np.nan)
    out["short_stop"] = np.where(out["fbo_sell"], prev_high.shift(1), np.nan)
    resistance = high.rolling(cfg.target_lookback).max().shift(1)
    support = low.rolling(cfg.target_lookback).min().shift(1)
    long_risk = close - out["long_stop"]
    short_risk = out["short_stop"] - close
    out["long_target"] = np.where(out["fbd_buy"], np.maximum(resistance, close + long_risk), np.nan)
    out["short_target"] = np.where(out["fbo_sell"], np.minimum(support, close - short_risk), np.nan)
    out["bb_upper"], out["bb_basis"], out["bb_lower"] = upper, basis, lower
    out["rsi"], out["macd"] = rsi, macd
    return out


def _cross(left: pd.Series, right: pd.Series) -> pd.Series:
    return (left > right) & (left.shift(1) <= right.shift(1))


def _rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def _dmi(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> tuple[pd.Series, pd.Series]:
    up, down = high.diff(), -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / length, adjust=False).mean().replace(0, np.nan)
    return 100 * plus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr, 100 * minus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr


def _validate(candles: pd.DataFrame, cfg: FakeBreakConfig) -> None:
    missing = {"open", "high", "low", "close", "volume"} - set(candles.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
    if min(cfg.level_lookback, cfg.bb_length, cfg.rsi_length, cfg.stochastic_length, cfg.dmi_length) < 2:
        raise ValueError("Indicator lengths must be at least 2")
    if not 0 <= cfg.min_confirmations <= 8:
        raise ValueError("min_confirmations must be between 0 and 8")
