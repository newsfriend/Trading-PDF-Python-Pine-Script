import unittest

import numpy as np
import pandas as pd

from python.geo_p_momentum import backtest_signals, compute_signals


def _sample_candles(rows=600):
    index = pd.date_range("2025-01-01", periods=rows, freq="15min")
    phase = np.arange(rows)
    close = pd.Series(
        2000.0 + np.linspace(0.0, 60.0, rows) + 12.0 * np.sin(phase / 9.0),
        index=index,
    )
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "volume": 1000.0 + 100.0 * np.cos(phase / 7.0),
        },
        index=index,
    )


class GeoPMomentumRuntimeTests(unittest.TestCase):
    def test_valid_ohlcv_runs_full_signal_and_backtest_pipeline(self):
        candles = _sample_candles()

        signals = compute_signals(candles)
        trades = backtest_signals(signals)

        self.assertEqual(len(signals), len(candles))
        self.assertTrue(
            {
                "buy_signal",
                "sell_signal",
                "long_stop",
                "short_stop",
                "long_target_1",
                "short_target_1",
            }.issubset(signals.columns)
        )
        self.assertIsInstance(trades, pd.DataFrame)

    def test_missing_required_ohlcv_column_is_rejected(self):
        candles = _sample_candles().drop(columns="volume")

        with self.assertRaisesRegex(ValueError, "volume"):
            compute_signals(candles)


if __name__ == "__main__":
    unittest.main()
