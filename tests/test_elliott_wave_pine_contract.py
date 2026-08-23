from pathlib import Path
import unittest


PINE_FILE = Path(__file__).resolve().parents[1] / "pine" / "elliott_wave_notes.pine"


class ElliottWavePineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PINE_FILE.read_text(encoding="utf-8")

    def test_candidate_state_is_the_default_engine(self):
        self.assertIn(
            'input.string("Candidate State (V4 Full Cycle)", "Engine mode"',
            self.source,
        )

    def test_important_context_comes_from_degree_source(self):
        self.assertIn("request.security", self.source)
        self.assertIn("degreeSourceTimeframe", self.source)
        self.assertIn("importantLookbackDays", self.source)

    def test_locked_origin_has_hard_invalidation_and_recount(self):
        self.assertIn('lastReasonCode := "W2_ORIGIN_BREAK"', self.source)
        self.assertIn("recountCount += 1", self.source)
        self.assertIn("searchFloorBar := bar_index", self.source)

    def test_later_raw_pivots_are_not_given_main_wave_numbers(self):
        self.assertIn('developingText := correctSide ? "2?" : "raw"', self.source)
        self.assertIn('lastReasonCode := "W2_CLASSIFIER_PENDING"', self.source)

    def test_core_impulse_uses_parent_state_gates(self):
        for state in (
            'engineStage := "W2_CORRECTION_CONTAINER"',
            'engineStage := "W3_FORMING"',
            'engineStage := "W4_CORRECTION_CONTAINER"',
            'engineStage := "W5_FORMING"',
            'engineStage := "LARGER_CORRECTION_CONTAINER"',
        ):
            self.assertIn(state, self.source)

    def test_wave5_is_locked_only_after_wave4_confirmation(self):
        wave4_confirmation = self.source.index('lastReasonCode := "W4_CONFIRMED"')
        wave5_lock = self.source.index("lockedW5Bar := latestBar")
        self.assertLess(wave4_confirmation, wave5_lock)

    def test_structure_specific_correction_ranges_are_present(self):
        self.assertIn("bRatio >= 0.01 and bRatio <= 0.618", self.source)
        self.assertIn("bRatio >= flatBMinRetrace", self.source)
        self.assertIn("bRatio <= flatBMaxRetrace", self.source)

    def test_locked_main_labels_include_complete_impulse(self):
        for label in ('text="2"', 'text="3"', 'text="4"', 'text="5"'):
            self.assertIn(label, self.source)

    def test_completed_impulse_opens_and_draws_larger_abc(self):
        self.assertIn('engineStage := "LARGER_CORRECTION_CONTAINER"', self.source)
        self.assertIn('lastReasonCode := "CORRECTION_COMPLETE"', self.source)
        for label in ('text="A"', 'text="B"', 'text="C"'):
            self.assertIn(label, self.source)

    def test_v4_closed_bar_alert_contract_is_present(self):
        for alert_name in (
            "EW FORMING",
            "EW CONFIRMED",
            "EW INVALID",
            "EW CONTROLLED RECOUNT",
            "EW CORRECTION COMPLETE",
            "EW HP BUY",
            "EW HP SELL",
        ):
            self.assertIn(f'alertcondition(stateChanged', self.source)
            self.assertIn(f'"{alert_name}"', self.source)

    def test_v4_time_windows_are_confirmation_gates(self):
        for helper in (
            "f_w2_time_pass",
            "f_w3_time_pass",
            "f_w4_time_pass",
            "f_w5_time_pass",
        ):
            self.assertIn(helper, self.source)
        for reason in (
            "W2_TIME_GATE_FAIL",
            "W3_TIME_GATE_FAIL",
            "W4_TIME_GATE_FAIL",
            "W5_TIME_GATE_FAIL",
        ):
            self.assertIn(reason, self.source)

    def test_hp_fib_opportunity_is_not_blocked_by_extended_w2_time(self):
        self.assertIn(
            'hpSignalState := deep and correctionConfirmed and hpSignalMode != "Disabled"',
            self.source,
        )
        self.assertNotIn(
            'hpSignalState := deep and correctionConfirmed and timePass',
            self.source,
        )

    def test_v4_six_triangle_families_are_classified(self):
        self.assertIn("f_eval_triangle", self.source)
        for subtype in (
            "HORIZONTAL_CONTRACTING",
            "IRREGULAR_CONTRACTING",
            "RUNNING_CONTRACTING",
            "HORIZONTAL_EXPANDING",
            "IRREGULAR_EXPANDING",
            "RUNNING_EXPANDING",
        ):
            self.assertIn(subtype, self.source)
        self.assertIn('text="D"', self.source)
        self.assertIn('text="E"', self.source)
        for field in (
            "lockedTriangleTargetNear",
            "lockedTriangleTargetFar",
            "lockedTriangleInvalidation",
        ):
            self.assertIn(field, self.source)
        self.assertIn("triangleInvalidLine = line.new", self.source)


if __name__ == "__main__":
    unittest.main()
