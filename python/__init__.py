"""Python implementation of the trading setup modules."""

from .geo_p_momentum import GeoPMomentumConfig, backtest_signals, compute_signals

__all__ = ["GeoPMomentumConfig", "compute_signals", "backtest_signals"]
