import unittest
from dataclasses import replace

import pandas as pd

from python.elliott_wave_notes import ElliottWaveConfig, compute_elliott_waves
from python.elliott_wave_parity import (
    PARITY_TITLES,
    build_python_parity,
    compare_tradingview_export,
    _daily_context,
)


class ElliottWaveParityTests(unittest.TestCase):
    def setUp(self):
        closes = [
            100, 104, 108, 103, 98, 94, 99, 105, 111, 106,
            101, 96, 102, 109, 116, 110, 104, 99, 106, 113,
            120, 114, 108, 102, 109, 117, 124, 118, 112, 106,
        ]
        self.market = pd.DataFrame(
            {
                "high": [value + 1.0 for value in closes],
                "low": [value - 1.0 for value in closes],
                "close": closes,
            },
            index=pd.date_range("2025-01-01", periods=len(closes), freq="D", tz="UTC"),
        )
        self.config = ElliottWaveConfig(
            pivot_left=1,
            pivot_right=1,
            min_swing_atr_multiple=0.0,
            min_swing_range_pct=0.0,
            important_atr_multiple=0.0,
            wave1_start_mode="Off",
            base_oscillator_mode="Off",
            degree_retrace=0.10,
        )

    def _matching_export(self):
        result = compute_elliott_waves(self.market, self.config)
        export = self.market.copy()
        for title, values in build_python_parity(result).items():
            export[title] = values
        return export

    def test_matching_replay_export_passes_all_parity_fields(self):
        report = compare_tradingview_export(self._matching_export(), self.config)

        self.assertTrue(report["passed"])
        self.assertEqual(report["total_mismatches"], 0)
        self.assertEqual([field["field"] for field in report["fields"]], list(PARITY_TITLES))

    def test_first_mismatch_is_reported_with_timestamp_and_values(self):
        export = self._matching_export()
        export.loc[export.index[8], PARITY_TITLES[1]] = 99

        report = compare_tradingview_export(export, self.config)

        self.assertFalse(report["passed"])
        self.assertEqual(report["total_mismatches"], 1)
        state_field = next(
            field for field in report["fields"] if field["field"] == PARITY_TITLES[1]
        )
        self.assertEqual(state_field["mismatches"], 1)
        self.assertEqual(state_field["first_mismatch"]["pine"], 99.0)

    def test_missing_parity_series_is_rejected(self):
        export = self._matching_export().drop(columns=[PARITY_TITLES[-1]])

        with self.assertRaisesRegex(ValueError, PARITY_TITLES[-1]):
            compare_tradingview_export(export, replace(self.config))

    def test_default_parity_uses_confirmed_daily_source_context(self):
        config = replace(
            ElliottWaveConfig(),
            important_context_mode="Source timeframe bars",
        )
        result = compute_elliott_waves(
            self.market,
            config,
            important_context=_daily_context(self.market),
        )
        export = self.market.copy()
        for title, values in build_python_parity(result).items():
            export[title] = values

        report = compare_tradingview_export(export)

        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
