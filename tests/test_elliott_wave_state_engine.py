import unittest

import pandas as pd

from python.elliott_wave_notes import (
    ElliottWaveConfig,
    _Swing,
    compute_elliott_waves,
    _run_candidate_state,
    _with_indicators,
)


def _swing(position, price, kind, *, important=False, macd_extreme=False):
    timestamp = pd.Timestamp("2025-01-01") + pd.Timedelta(days=position)
    confirmed = timestamp + pd.Timedelta(days=1)
    return _Swing(
        position=position,
        confirmed_position=position + 1,
        index=timestamp,
        confirmed_index=confirmed,
        price=float(price),
        kind=kind,
        atr=2.0,
        macd_hist=-4.0 if kind == -1 else 4.0,
        rsi=25.0 if kind == -1 else 75.0,
        macd_extreme=macd_extreme,
        important_extreme=important,
        important_range=100.0,
        important_high=100.0,
        important_low=0.0,
    )


def _confirmed_wave1():
    return [
        _swing(0, 0, -1, important=True, macd_extreme=True),
        _swing(1, 25, 1),
        _swing(2, 15, -1),
        _swing(3, 42, 1),
        _swing(4, 30, -1),
        _swing(5, 62, 1),
    ]


class ElliottWavePhase1Tests(unittest.TestCase):
    def setUp(self):
        self.config = ElliottWaveConfig(important_context_mode="Legacy bars")

    def test_t01_qualified_base_locks_after_five_move_wave1(self):
        state = _run_candidate_state(_confirmed_wave1(), self.config)

        self.assertEqual(state["final_state"], "CONFIRMED")
        self.assertEqual(state["active"]["start_idx"], 0)
        self.assertEqual(state["active"]["end_idx"], 5)
        self.assertEqual(state["active"]["internal_count"], 5)
        self.assertAlmostEqual(state["active"]["degree_progress"], 0.62)

    def test_t04_origin_break_invalidates_and_starts_controlled_recount(self):
        swings = _confirmed_wave1() + [_swing(6, -1, -1)]
        state = _run_candidate_state(swings, self.config)

        self.assertIsNone(state["active"])
        self.assertEqual(state["recount_count"], 1)
        self.assertEqual(state["last_reason_code"], "W2_ORIGIN_BREAK")
        self.assertTrue(
            any(
                event["values"].get("ew_engine_state") == "INVALID"
                for event in state["events"]
            )
        )

    def test_t25_minor_swings_are_not_promoted_to_main_labels(self):
        swings = _confirmed_wave1() + [
            _swing(6, 40, -1),
            _swing(7, 70, 1),
        ]
        state = _run_candidate_state(swings, self.config)

        later_events = [
            event for event in state["events"] if event["index"] in {swings[6].index, swings[7].index}
        ]
        self.assertTrue(later_events)
        self.assertTrue(
            all(
                event["values"].get("ew_engine_state") in {"FORMING", "ALTERNATE"}
                for event in later_events
            )
        )
        self.assertTrue(
            all(event["values"].get("ew_candidate_label") != "3" for event in later_events)
        )

    def test_t28_locked_base_and_wave1_do_not_move_without_invalidation(self):
        swings = _confirmed_wave1() + [
            _swing(6, 38, -1),
            _swing(7, 75, 1),
            _swing(8, 35, -1),
        ]
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["recount_count"], 0)
        self.assertEqual(state["active"]["start_idx"], 0)
        self.assertEqual(state["active"]["end_idx"], 5)
        self.assertEqual(state["active"]["base_price"], 0.0)

    def test_t29_important_context_uses_calendar_days_not_chart_bars(self):
        candles = pd.DataFrame(
            {
                "high": [100.0, 20.0, 22.0],
                "low": [90.0, 10.0, 12.0],
                "close": [95.0, 15.0, 18.0],
            },
            index=pd.to_datetime(["2024-01-01", "2024-06-01", "2024-06-02"]),
        )
        calendar = _with_indicators(candles, ElliottWaveConfig())
        legacy = _with_indicators(candles, self.config)

        self.assertEqual(calendar.loc[pd.Timestamp("2024-06-01"), "_ew_important_high"], 20.0)
        self.assertEqual(legacy.loc[pd.Timestamp("2024-06-01"), "_ew_important_high"], 100.0)

    def test_public_api_exports_raw_main_and_lifecycle_fields(self):
        closes = [
            100, 104, 108, 103, 98, 94, 99, 105, 111, 106,
            101, 96, 102, 109, 116, 110, 104, 99, 106, 113,
            120, 114, 108, 102, 109, 117, 124, 118, 112, 106,
        ]
        candles = pd.DataFrame(
            {
                "high": [value + 1.0 for value in closes],
                "low": [value - 1.0 for value in closes],
                "close": closes,
            },
            index=pd.date_range("2025-01-01", periods=len(closes), freq="D"),
        )
        result = compute_elliott_waves(
            candles,
            ElliottWaveConfig(
                pivot_left=1,
                pivot_right=1,
                min_swing_atr_multiple=0.0,
                min_swing_range_pct=0.0,
                important_atr_multiple=0.0,
                wave1_start_mode="Off",
                base_oscillator_mode="Off",
                degree_retrace=0.10,
            ),
        )

        for column in (
            "ew_raw_pivot",
            "ew_pivot",
            "ew_engine_state",
            "ew_reason_code",
            "ew_base_locked",
            "ew_recount_count",
        ):
            self.assertIn(column, result.columns)
        self.assertEqual(result.attrs["elliott_wave_state"]["engine"], "Candidate State")

    def test_rsi_seed_waits_for_full_change_window(self):
        candles = pd.DataFrame(
            {
                "high": [value + 1.0 for value in range(20)],
                "low": [value - 1.0 for value in range(20)],
                "close": [float(value) for value in range(20)],
            },
            index=pd.date_range("2025-01-01", periods=20, freq="D"),
        )
        enriched = _with_indicators(candles, ElliottWaveConfig(rsi_length=14))

        self.assertTrue(enriched["_ew_rsi"].iloc[:14].isna().all())
        self.assertEqual(enriched["_ew_rsi"].iloc[14], 100.0)


if __name__ == "__main__":
    unittest.main()
