"""Python implementation of the trading setup modules."""

from .elliott_wave_notes import ElliottWaveConfig, compute_elliott_waves
from .client_swing_structure import ClientSwingStructure, StructuralPivot
from .fake_bo_bd import (
    FakeBreakConfig,
    backtest_fake_break_signals,
    compute_fake_break_signals,
)
from .geo_p_momentum import GeoPMomentumConfig, backtest_signals, compute_signals

__all__ = [
    "GeoPMomentumConfig",
    "compute_signals",
    "backtest_signals",
    "ElliottWaveConfig",
    "compute_elliott_waves",
    "ClientSwingStructure",
    "StructuralPivot",
    "FakeBreakConfig",
    "compute_fake_break_signals",
    "backtest_fake_break_signals",
]
