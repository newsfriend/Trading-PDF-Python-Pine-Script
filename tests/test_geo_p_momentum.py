import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from python.geo_p_momentum import (
    TRADE_COLUMNS,
    GeoPMomentumConfig,
    _infer_timeframe,
    _pdf_timeframes,
    _to_pandas_resample_rule,
    backtest_signals,
    compute_signals,
)


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
        self.assertEqual(tuple(trades.columns), TRADE_COLUMNS)

    def test_missing_required_ohlcv_column_is_rejected(self):
        candles = _sample_candles().drop(columns="volume")

        with self.assertRaisesRegex(ValueError, "volume"):
            compute_signals(candles)

    def test_pdf_auto_timeframes_match_pine_for_every_chart_family(self):
        expected = {
            "3": ("15", "5"),
            "5": ("60", "15"),
            "15": ("240", "60"),
            "60": ("D", "240"),
            "240": ("W", "D"),
            "D": ("M", "W"),
            "W": ("M", "M"),
            "M": ("M", "M"),
            "3M": ("3M", "3M"),
        }
        self.assertEqual(
            {timeframe: _pdf_timeframes(timeframe) for timeframe in expected},
            expected,
        )

    def test_calendar_timeframe_inference_recognizes_weekly_and_monthly_data(self):
        weekly = pd.date_range("2025-01-05", periods=5, freq="W")
        monthly = pd.date_range("2025-01-31", periods=5, freq="ME")
        self.assertEqual(_infer_timeframe(weekly), "W")
        self.assertEqual(_infer_timeframe(monthly), "M")
        self.assertIsInstance(_to_pandas_resample_rule("M"), pd.offsets.MonthEnd)

    def test_disabled_line2_does_not_require_datetime_resampling(self):
        candles = _sample_candles().reset_index(drop=True)
        config = GeoPMomentumConfig(
            timeframe_mode="Manual",
            wave_timeframe="60",
            use_line2_mtf_refinement=False,
        )
        signals = compute_signals(candles, config)
        self.assertEqual(len(signals), len(candles))

    def test_manual_context_cannot_be_lower_than_the_chart(self):
        with self.assertRaisesRegex(ValueError, "Manual Tide timeframe"):
            compute_signals(
                _sample_candles(),
                GeoPMomentumConfig(
                    timeframe_mode="Manual",
                    chart_timeframe="60",
                    tide_timeframe="15",
                ),
            )

    def test_confirmed_signals_are_prefix_invariant(self):
        candles = _sample_candles()
        full = compute_signals(candles)
        prefix = compute_signals(candles.iloc[:420])
        for column in (
            "raw_buy_signal",
            "raw_sell_signal",
            "buy_signal",
            "sell_signal",
            "line2_buy_setup",
            "line2_sell_setup",
        ):
            pd.testing.assert_series_equal(
                prefix[column],
                full.loc[prefix.index, column],
                check_names=False,
            )

    def test_invalid_market_data_and_config_are_rejected_early(self):
        candles = _sample_candles()
        duplicated = pd.concat([candles.iloc[:1], candles])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compute_signals(duplicated)

        invalid_range = candles.copy()
        invalid_range.iloc[0, invalid_range.columns.get_loc("high")] = (
            invalid_range.iloc[0]["low"] - 1.0
        )
        with self.assertRaisesRegex(ValueError, "high/low"):
            compute_signals(invalid_range)

        with self.assertRaisesRegex(ValueError, "min_better_confirmations"):
            compute_signals(
                candles,
                replace(GeoPMomentumConfig(), min_better_confirmations=5),
            )


class GeoPMomentumPineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.sources = {
            name: (root / "pine" / name).read_text(encoding="utf-8")
            for name in ("geo_p_momentum.pine", "geo_p_momentum_strategy.pine")
        }

    def test_pine_auto_timeframe_branches_match_the_python_router(self):
        required_tokens = (
            'timeframe.multiplier <= 3 ? "5"',
            'timeframe.multiplier <= 5 ? "15"',
            'timeframe.multiplier <= 15 ? "60"',
            'timeframe.multiplier <= 60 ? "240"',
            'timeframe.multiplier <= 3 ? "15"',
            'timeframe.multiplier <= 5 ? "60"',
            'timeframe.multiplier <= 15 ? "240"',
            'timeframe.multiplier <= 60 ? "D"',
            "else if timeframe.isdaily",
            "else if timeframe.isweekly",
        )
        for name, source in self.sources.items():
            with self.subTest(script=name):
                for token in required_tokens:
                    self.assertIn(token, source)

    def test_pine_mtf_requests_use_confirmed_higher_timeframe_values(self):
        for name, source in self.sources.items():
            with self.subTest(script=name):
                self.assertIn("f_tide_values(sourceOffset)", source)
                self.assertIn("f_wave_rsi(sourceOffset)", source)
                self.assertIn("tideBuy[sourceOffset]", source)
                self.assertIn("ta.rsi(close, rsiLength)[sourceOffset]", source)
                self.assertIn("tideSourceOffset = timeframe.in_seconds(tideTf)", source)
                self.assertIn("waveSourceOffset = timeframe.in_seconds(waveTf)", source)
                self.assertIn("invalidManualContext", source)
                self.assertIn("runtime.error", source)
                self.assertGreaterEqual(source.count("barmerge.lookahead_on"), 2)


if __name__ == "__main__":
    unittest.main()
