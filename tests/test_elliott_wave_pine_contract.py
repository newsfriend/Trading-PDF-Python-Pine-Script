from pathlib import Path
import unittest


PINE_FILE = Path(__file__).resolve().parents[1] / "pine" / "elliott_wave_notes.pine"


class ElliottWavePineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PINE_FILE.read_text(encoding="utf-8")

    def test_candidate_state_is_the_default_engine(self):
        self.assertIn(
            'input.string("Candidate State (Core Impulse)", "Engine mode"',
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
            'engineStage := "IMPULSE_CONFIRMED"',
        ):
            self.assertIn(state, self.source)

    def test_wave5_is_locked_only_after_wave4_confirmation(self):
        wave4_confirmation = self.source.index('lastReasonCode := "W4_CONFIRMED"')
        wave5_lock = self.source.index("lockedW5Bar := latestBar")
        self.assertLess(wave4_confirmation, wave5_lock)

    def test_structure_specific_correction_ranges_are_present(self):
        self.assertIn("bRatio >= 0.01 and bRatio <= 0.50", self.source)
        self.assertIn("bRatio >= flatBMinRetrace", self.source)
        self.assertIn("bRatio <= flatBMaxRetrace", self.source)

    def test_locked_main_labels_include_complete_impulse(self):
        for label in ('text="2"', 'text="3"', 'text="4"', 'text="5"'):
            self.assertIn(label, self.source)


if __name__ == "__main__":
    unittest.main()
