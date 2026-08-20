"""Python implementation of the trading setup modules."""

from .elliott_wave_notes import ElliottWaveConfig, compute_elliott_waves
from .geo_p_momentum import GeoPMomentumConfig, backtest_signals, compute_signals

__all__ = [
    "GeoPMomentumConfig",
    "compute_signals",
    "backtest_signals",
    "ElliottWaveConfig",
    "compute_elliott_waves",
]
