import unittest
from dataclasses import replace

import pandas as pd

from python.elliott_wave_notes import (
    ElliottWaveConfig,
    _Swing,
    compute_elliott_waves,
    _run_candidate_state,
    _evaluate_correction,
    _evaluate_triangle_correction,
    _with_indicators,
)


def _swing(
    position,
    price,
    kind,
    *,
    important=False,
    macd_extreme=False,
    macd_hist=None,
):
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
        macd_hist=(
            float(macd_hist)
            if macd_hist is not None
            else (-4.0 if kind == -1 else 4.0)
        ),
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


def _append_prices(swings, prices, *, final_macd=None, final_extreme=False):
    for offset, price in enumerate(prices):
        position = swings[-1].position + 1
        kind = -swings[-1].kind
        is_final = offset == len(prices) - 1
        swings.append(
            _swing(
                position,
                price,
                kind,
                macd_hist=final_macd if is_final else None,
                macd_extreme=final_extreme if is_final else False,
            )
        )
    return swings


def _through_w2():
    swings = _confirmed_wave1()
    _append_prices(swings, [58, 60, 54, 56, 50])  # Zig-Zag A: 5 moves
    _append_prices(swings, [55, 52, 56])  # B: 3 moves, 50% of A
    _append_prices(swings, [50, 53, 46, 49, 42])  # C: 5 moves
    return swings


def _through_w3():
    swings = _through_w2()
    _append_prices(swings, [75, 60, 100, 80, 145], final_macd=12, final_extreme=True)
    return swings


def _through_w4():
    swings = _through_w3()
    _append_prices(swings, [135, 140, 125])  # Flat A: 3 moves
    _append_prices(swings, [135, 128, 140])  # B: 3 moves, 75% of A
    _append_prices(swings, [132, 136, 120, 125, 110])  # C: 5 moves
    return swings


def _through_w5():
    swings = _through_w4()
    _append_prices(swings, [125, 115, 145, 130, 175], final_macd=5)
    return swings


def _through_larger_abc():
    swings = _through_w5()
    _append_prices(swings, [160, 168, 150, 158, 140])  # A: 5 moves
    _append_prices(swings, [150, 145, 157.5])  # B: 3 moves, 50% of A
    _append_prices(swings, [145, 150, 130, 138, 115])  # C: 5 moves
    return swings


def _contracting_triangle_from(starting_swings):
    swings = list(starting_swings)
    _append_prices(swings, [125, 135, 95])
    _append_prices(swings, [110, 100, 130])
    _append_prices(swings, [115, 125, 105])
    _append_prices(swings, [115, 110, 123])
    _append_prices(swings, [112, 118, 108])
    return swings


def _triangle_from_endpoints(endpoints):
    swings = [_swing(0, 100, 1)]
    for target in endpoints:
        current = swings[-1].price
        if swings[-1].kind == 1:
            fillers = [(current + target) / 2.0, max(current, target) + 1.0, target]
        else:
            fillers = [(current + target) / 2.0, min(current, target) - 1.0, target]
        _append_prices(swings, fillers)
    return swings


def _mirror_bearish(swings):
    return [
        replace(
            swing,
            price=100.0 - swing.price,
            kind=-swing.kind,
            macd_hist=-swing.macd_hist,
            rsi=100.0 - swing.rsi,
        )
        for swing in swings
    ]


class ElliottWaveCandidateStateTests(unittest.TestCase):
    def setUp(self):
        self.config = ElliottWaveConfig(important_context_mode="Legacy bars")

    def test_t01_qualified_base_locks_after_five_move_wave1(self):
        state = _run_candidate_state(_confirmed_wave1(), self.config)

        self.assertEqual(state["final_state"], "W2_CORRECTION_CONTAINER")
        self.assertEqual(state["active"]["start_idx"], 0)
        self.assertEqual(state["active"]["end_idx"], 5)
        self.assertEqual(state["active"]["internal_count"], 5)
        self.assertAlmostEqual(state["active"]["degree_progress"], 0.62)

    def test_t02_normal_w2_requires_internal_correction_completion(self):
        state = _run_candidate_state(_through_w2(), self.config)

        self.assertEqual(state["active"]["parent_state"], "W3_FORMING")
        self.assertEqual(state["active"]["waves"]["2"]["pattern"], "Zig-Zag")
        self.assertEqual(state["active"]["waves"]["2"]["internal_pattern"], "5-3-5")
        self.assertGreaterEqual(state["active"]["waves"]["2"]["fib_value"], 0.236)
        self.assertLessEqual(state["active"]["waves"]["2"]["fib_value"], 0.812)

    def test_v4_w2_time_gate_blocks_price_only_confirmation(self):
        swings = _through_w2()
        delayed = swings[-1]
        swings[-1] = replace(
            delayed,
            position=40,
            confirmed_position=41,
            index=pd.Timestamp("2025-02-10"),
            confirmed_index=pd.Timestamp("2025-02-11"),
        )
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["active"]["parent_state"], "W2_CORRECTION_CONTAINER")
        self.assertNotIn("2", state["active"]["waves"])
        self.assertEqual(state["last_reason_code"], "W2_TIME_GATE_FAIL")

    def test_client_hp_fib_signal_survives_extended_wave2_timing(self):
        swings = _through_w2()
        delayed = swings[-1]
        swings[-1] = replace(
            delayed,
            price=20.0,
            position=40,
            confirmed_position=41,
            index=pd.Timestamp("2025-02-10"),
            confirmed_index=pd.Timestamp("2025-02-11"),
        )
        state = _run_candidate_state(swings, self.config)
        final_event = state["events"][-1]["values"]

        self.assertEqual(state["active"]["parent_state"], "W2_CORRECTION_CONTAINER")
        self.assertEqual(state["last_reason_code"], "W2_TIME_GATE_FAIL")
        self.assertEqual(final_event["ew_engine_state"], "FORMING")
        self.assertEqual(final_event["ew_hp_signal"], "HP BUY ELIGIBLE")

    def test_client_bearish_hp_sell_survives_extended_wave2_timing(self):
        bullish = _through_w2()
        delayed = bullish[-1]
        bullish[-1] = replace(
            delayed,
            price=20.0,
            position=40,
            confirmed_position=41,
            index=pd.Timestamp("2025-02-10"),
            confirmed_index=pd.Timestamp("2025-02-11"),
        )
        state = _run_candidate_state(_mirror_bearish(bullish), self.config)
        final_event = state["events"][-1]["values"]

        self.assertEqual(state["active"]["parent_state"], "W2_CORRECTION_CONTAINER")
        self.assertEqual(state["last_reason_code"], "W2_TIME_GATE_FAIL")
        self.assertEqual(final_event["ew_engine_state"], "FORMING")
        self.assertEqual(final_event["ew_hp_signal"], "HP SELL ELIGIBLE")

    def test_t03_microscopic_w2_is_a_separate_subtype(self):
        swings = _confirmed_wave1()
        _append_prices(swings, [60, 61, 59, 60.5, 58])
        _append_prices(swings, [60, 59, 60])
        _append_prices(swings, [58, 59.5, 56, 58, 53.32])
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["active"]["waves"]["2"]["subtype"], "W2_MICROSCOPIC")

    def test_t05_flat_b_can_retrace_up_to_111_percent(self):
        swings = _confirmed_wave1()
        _append_prices(swings, [52, 57, 42])
        _append_prices(swings, [55, 48, 64.2])
        _append_prices(swings, [55, 60, 50, 57, 42])
        state = _run_candidate_state(swings, self.config)

        wave2 = state["active"]["waves"]["2"]
        self.assertEqual(wave2["pattern"], "Flat")
        self.assertIn("B=111.00%", wave2["note"])

    def test_t06_flat_b_above_111_percent_stays_unconfirmed(self):
        swings = _confirmed_wave1()
        _append_prices(swings, [52, 57, 42])
        _append_prices(swings, [55, 48, 65])
        _append_prices(swings, [55, 60, 50, 57, 42])
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["active"]["parent_state"], "W2_CORRECTION_CONTAINER")
        self.assertNotIn("2", state["active"]["waves"])
        self.assertEqual(state["last_reason_code"], "FLAT_B_GT_111")

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

    def test_t07_trending_w3_is_classified_not_warned(self):
        state = _run_candidate_state(_through_w3(), self.config)

        self.assertEqual(state["active"]["parent_state"], "W4_CORRECTION_CONTAINER")
        self.assertEqual(state["active"]["waves"]["3"]["subtype"], "W3_TRENDING")

    def test_t08_terminal_w3_requires_internal_overlap(self):
        swings = _through_w2()
        _append_prices(swings, [85, 70, 100, 80, 104], final_macd=8)
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["active"]["waves"]["3"]["subtype"], "W3_TERMINAL")

    def test_t09_extended_w3_keeps_one_parent_wave(self):
        swings = _through_w2()
        _append_prices(
            swings,
            [70, 55, 85, 75, 100, 80, 120, 90, 145],
            final_macd=12,
            final_extreme=True,
        )
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["active"]["waves"]["3"]["internal_count"], 9)
        self.assertEqual(state["active"]["waves"]["3"]["subtype"], "W3_TRENDING_EXTENDED")
        self.assertNotIn("4", state["active"]["waves"])

    def test_t10_normal_w4_completes_before_w5_can_start(self):
        state = _run_candidate_state(_through_w4(), self.config)

        self.assertEqual(state["active"]["parent_state"], "W5_FORMING")
        self.assertEqual(state["active"]["waves"]["4"]["pattern"], "Flat")
        self.assertNotIn("5", state["active"]["waves"])

    def test_t10b_normal_w4_overlap_is_rejected(self):
        swings = _through_w3()
        _append_prices(swings, [120, 130, 90])
        _append_prices(swings, [120, 100, 131.25])
        _append_prices(swings, [110, 120, 90, 105, 60])
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["active"]["parent_state"], "W4_CORRECTION_CONTAINER")
        self.assertNotIn("4", state["active"]["waves"])
        self.assertEqual(state["last_reason_code"], "W4_NORMAL_OVERLAP")

    def test_t11_incomplete_complex_w4_cannot_print_wave5(self):
        swings = _through_w3()
        _append_prices(swings, [135, 140, 125, 135, 128, 140, 132, 136, 120, 125])
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["active"]["parent_state"], "W4_CORRECTION_CONTAINER")
        self.assertNotIn("4", state["active"]["waves"])
        self.assertNotIn("5", state["active"]["waves"])

    def test_t12_normal_w5_checks_projection_and_degree_divergence(self):
        state = _run_candidate_state(_through_w5(), self.config)

        self.assertEqual(state["active"]["parent_state"], "LARGER_CORRECTION_CONTAINER")
        self.assertEqual(state["active"]["waves"]["5"]["subtype"], "W5_NORMAL")
        self.assertEqual(
            state["active"]["waves"]["5"]["macd_state"],
            "W3/W5 DIVERGENCE PASS",
        )

    def test_v4_larger_correction_locks_abc_after_wave5(self):
        state = _run_candidate_state(_through_larger_abc(), self.config)

        self.assertEqual(state["active"]["parent_state"], "CORRECTION_CONFIRMED")
        self.assertEqual(list(state["active"]["waves"]), ["0", "1", "2", "3", "4", "5", "A", "B", "C"])
        self.assertEqual(state["active"]["waves"]["C"]["reason_code"], "C_CONFIRMED")
        self.assertEqual(state["last_reason_code"], "CORRECTION_COMPLETE")

    def test_v4_horizontal_contracting_triangle_uses_five_corrective_legs(self):
        swings = _contracting_triangle_from(_through_w3())
        start_idx = len(_through_w3()) - 1
        triangle = _evaluate_triangle_correction(swings, start_idx, len(swings) - 1)

        self.assertTrue(triangle["confirmed"])
        self.assertEqual(triangle["subtype"], "HORIZONTAL_CONTRACTING")
        self.assertEqual(triangle["labels"], ("A", "B", "C", "D", "E"))
        self.assertEqual(triangle["internal_pattern"], "3-3-3-3-3")
        self.assertGreater(triangle["thrust_max"], triangle["thrust_min"])
        self.assertEqual(triangle["invalidation_price"], 108.0)
        self.assertGreater(triangle["thrust_target_far"], triangle["thrust_target_near"])

    def test_v4_completed_triangle_confirms_wave4_before_wave5(self):
        state = _run_candidate_state(
            _contracting_triangle_from(_through_w3()), self.config
        )

        self.assertEqual(state["active"]["parent_state"], "W5_FORMING")
        self.assertEqual(state["active"]["waves"]["4"]["pattern"], "Triangle")
        self.assertEqual(
            state["active"]["waves"]["4"]["subtype"],
            "W4_HORIZONTAL_CONTRACTING",
        )
        self.assertEqual(
            state["active"]["waves"]["4"]["invalidation_price"], 108.0
        )
        self.assertGreater(
            state["active"]["waves"]["4"]["target_far"],
            state["active"]["waves"]["4"]["target_near"],
        )

    def test_v4_all_six_triangle_size_and_boundary_families(self):
        fixtures = {
            "HORIZONTAL_CONTRACTING": [50, 85, 60, 78, 65],
            "IRREGULAR_CONTRACTING": [70, 120, 85, 110, 92],
            "RUNNING_CONTRACTING": [70, 120, 85, 125, 95],
            "HORIZONTAL_EXPANDING": [90, 105, 85, 110, 80],
            "IRREGULAR_EXPANDING": [80, 90, 70, 100, 60],
            "RUNNING_EXPANDING": [80, 110, 85, 120, 75],
        }
        for expected, endpoints in fixtures.items():
            with self.subTest(expected=expected):
                swings = _triangle_from_endpoints(endpoints)
                triangle = _evaluate_triangle_correction(swings, 0, len(swings) - 1)
                self.assertTrue(triangle["confirmed"])
                self.assertEqual(triangle["subtype"], expected)

    def test_v4_triangle_is_never_considered_for_wave2(self):
        swings = _contracting_triangle_from(_confirmed_wave1())
        start_idx = len(_confirmed_wave1()) - 1
        correction = _evaluate_correction(swings, start_idx, len(swings) - 1, self.config)

        self.assertNotEqual(correction["primary"], "Triangle")

    def test_t13_truncated_w5_uses_double_extension_context(self):
        swings = [_swing(0, 0, -1, important=True, macd_extreme=True)]
        _append_prices(swings, [15, 8, 30, 18, 45, 25, 55, 35, 62])
        _append_prices(swings, [58, 60, 54, 56, 50])
        _append_prices(swings, [55, 52, 56])
        _append_prices(swings, [50, 53, 46, 49, 42])
        _append_prices(swings, [70, 55, 85, 75, 100, 80, 120, 90, 145], final_macd=12)
        _append_prices(swings, [135, 140, 125])
        _append_prices(swings, [135, 128, 140])
        _append_prices(swings, [132, 136, 120, 125, 110])
        _append_prices(swings, [120, 113, 130, 118, 138], final_macd=5)
        state = _run_candidate_state(swings, self.config)

        self.assertEqual(state["active"]["waves"]["1"]["internal_count"], 9)
        self.assertEqual(state["active"]["waves"]["3"]["internal_count"], 9)
        self.assertEqual(state["active"]["waves"]["5"]["subtype"], "W5_TRUNCATED")

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
