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

    def test_v4_point0_and_w1_are_separate_lifecycle_states(self):
        for token in (
            'input.string("Significant degree swing", "Start filter"',
            'engineStage := "W1_FORMING"',
            'lastReasonCode := "W1_DEVELOPED"',
            'lastReasonCode := "W1_CONFIRMED"',
            'engineStage := "W2_CORRECTION_CONTAINER"',
            'f_find_developed_base',
            'lockedW1Bar := na',
            'if not na(lockedW1Bar)',
        ):
            self.assertIn(token, self.source)
        developed = self.source.index('lastReasonCode := "W1_DEVELOPED"')
        confirmed = self.source.index('lastReasonCode := "W1_CONFIRMED"', developed)
        self.assertLess(developed, confirmed)

    def test_v4_w1_time_and_degree_significance_are_hard_gates(self):
        for token in (
            "degreePivotAtrMultiple",
            "degreePivotRangePct",
            "swingDegreeSignificant",
            "swingImportantHighBar",
            "swingImportantLowBar",
            '"W1_TIME_61_8_AT_HALF"',
            '"W1_TIME_100_AT_EQUAL"',
            '"W1_TIME_GATE_FAIL"',
            "timePass and atrOk and originOk",
        ):
            self.assertIn(token, self.source)

    def test_v4_point0_oscillator_is_ranking_evidence_only(self):
        self.assertIn("candidateRank :=", self.source)
        self.assertIn("oscillatorEvidence ? 10000", self.source)
        self.assertNotIn(
            "importantOk and degreeOk and timePass and atrOk and oscillatorOk",
            self.source,
        )

    def test_dashboard_preserves_original_positions_in_the_foreground(self):
        self.assertIn(
            'indicator("Elliott Wave Notes Overlay v4.2 Multi-Cycle", overlay=true, behind_chart=false',
            self.source,
        )
        self.assertIn(
            'input.string("Hidden", "Dashboard", options=["Compact", "Full", "Hidden"]',
            self.source,
        )
        self.assertIn(
            'table.new(position.top_right, 2, 7',
            self.source,
        )
        self.assertIn(
            'table.new(position.bottom_right, 5, 10',
            self.source,
        )
        for color_name in (
            "dashboardHeaderColor",
            "dashboardBodyColor",
            "dashboardSelectedColor",
        ):
            self.assertIn(f"{color_name} = color.rgb(", self.source)
        self.assertIn(
            "routeColor = selectedRoute ? dashboardSelectedColor : dashboardBodyColor",
            self.source,
        )
        drawing_calls = [
            line
            for line in self.source.splitlines()
            if "line.new(" in line or "label.new(" in line
        ]
        self.assertTrue(drawing_calls)
        self.assertTrue(all("force_overlay=true" in line for line in drawing_calls))
        self.assertIn('dashboardMode == "Full"', self.source)
        self.assertIn('dashboardMode == "Compact"', self.source)

    def test_important_context_comes_from_degree_source(self):
        self.assertIn("request.security", self.source)
        self.assertIn("degreeSourceTimeframe", self.source)
        self.assertIn("importantLookbackDays", self.source)
        self.assertIn(
            "degreeSourceOffset = timeframe.in_seconds(degreeSourceTimeframe)",
            self.source,
        )
        self.assertIn(
            "ta.highest(high, importantLookbackDays)[degreeSourceOffset]",
            self.source,
        )
        self.assertIn(
            "ta.lowest(low, importantLookbackDays)[degreeSourceOffset]",
            self.source,
        )
        self.assertIn("invalidManualDegree", self.source)
        self.assertIn("runtime.error", self.source)

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
        self.assertIn("f_flat_a_pass", self.source)
        self.assertIn('"FLAT_A_LT_38_2"', self.source)
        self.assertIn(">= flatAMinRetrace", self.source)

    def test_simple_corrections_use_mandatory_time_gates_and_subtypes(self):
        for token in (
            "bTimePass",
            "cTimePass",
            "10.0 * aDuration",
            "0.25 * abDuration",
            '"B_TIME_GATE_FAIL"',
            '"C_TIME_GATE_FAIL"',
            '"ZIG_ZAG_NORMAL"',
            '"ZIG_ZAG_ELONGATED"',
            '"FLAT_NORMAL"',
            '"FLAT_ELONGATED"',
            '"FLAT_STRONG_IRREGULAR"',
            '"FLAT_RUNNING"',
        ):
            self.assertIn(token, self.source)

    def test_locked_main_labels_include_complete_impulse(self):
        for label in (
            'text=f_parent_correction_label("2", lockedW2Pattern)',
            'text="3"',
            'text=f_parent_correction_label("4", lockedW4Pattern)',
            'text="5"',
        ):
            self.assertIn(label, self.source)

    def test_completed_impulse_opens_and_draws_larger_abc(self):
        self.assertIn('engineStage := "LARGER_CORRECTION_CONTAINER"', self.source)
        self.assertIn('lastReasonCode := "CORRECTION_COMPLETE"', self.source)
        self.assertIn("f_locked_correction_label", self.source)
        for position in range(3):
            self.assertIn(f'"(" + f_locked_correction_label({position}) + ")"', self.source)

    def test_completed_cycles_are_archived_and_redrawn_without_recounting(self):
        for token in (
            'input.int(3, "Completed cycles retained"',
            "var historyBars = array.new_int()",
            "var historyCycleIds = array.new_int()",
            "f_archive_locked_cycle",
            "f_redraw_history()",
            'engineStage == "CORRECTION_CONFIRMED"',
            "searchFloorBar := terminalBar",
            "completedCycleCount += 1",
        ):
            self.assertIn(token, self.source)
        archive_call = self.source.index(
            "f_archive_locked_cycle(completedCycleCount, oldestCycleToKeep)"
        )
        release = self.source.index("baseLocked := false", archive_call)
        redraw = self.source.index("f_redraw_history()", self.source.index("f_redraw_candidate"))
        self.assertLess(archive_call, release)
        self.assertLess(redraw, archive_call)

    def test_active_and_archived_cycles_share_reference_label_grammar(self):
        for color in (
            "color.rgb(255, 145, 0)",
            "color.rgb(235, 62, 71)",
            "correctionLineColor",
        ):
            self.assertIn(color, self.source)
        self.assertIn('displayText = isCorrectionNode ? "(" + nodeText + ")"', self.source)
        self.assertIn("f_parent_correction_label", self.source)
        self.assertIn('f_parent_correction_label("2", lockedW2Pattern)', self.source)
        self.assertIn('f_parent_correction_label("4", lockedW4Pattern)', self.source)

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

    def test_v4_exports_hidden_replay_parity_series(self):
        for title in (
            "EW PARITY confirmation event",
            "EW PARITY candidate state code",
            "EW PARITY parent state code",
            "EW PARITY confirmed label code",
            "EW PARITY completed cycle count",
            "EW PARITY recount count",
            "EW PARITY base locked",
            "EW PARITY Point 0 price",
            "EW PARITY Wave 1 price",
            "EW PARITY Wave 2 price",
            "EW PARITY Wave 3 price",
            "EW PARITY Wave 4 price",
            "EW PARITY Wave 5 price",
            "EW PARITY current Fib value",
            "EW PARITY current time value",
        ):
            self.assertIn(f'"{title}"', self.source)
        self.assertIn("display=display.data_window", self.source)
        self.assertIn("f_candidate_state_code", self.source)
        self.assertIn("f_parent_state_code", self.source)

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
        self.assertIn('"(" + f_locked_correction_label(3) + ")"', self.source)
        self.assertIn('"(" + f_locked_correction_label(4) + ")"', self.source)
        for field in (
            "lockedTriangleTargetNear",
            "lockedTriangleTargetFar",
            "lockedTriangleInvalidation",
        ):
            self.assertIn(field, self.source)
        self.assertIn("triangleInvalidLine = line.new", self.source)
        for token in (
            'f_eval_triangle(w3Index, latestIndex, true)',
            '"TRIANGLE_BD_BREAK_PENDING"',
            "apexPosition",
            "acTouches <= 5 and bdTouches <= 5",
            "observedClose > bdValue",
            "triangleTerminalIndex",
        ):
            self.assertIn(token, self.source)

    def test_v4_correction_ranking_prefers_completed_mandatory_gates(self):
        self.assertIn("f_correction_rank", self.source)
        self.assertIn('pattern == "W-X-Y-XX-Z" ? 12', self.source)
        self.assertIn(
            "f_correction_rank(complexPrimary) > f_correction_rank(correctionPrimary)",
            self.source,
        )

    def test_v4_channel_cluster_confidence_and_fbd_support_are_exposed(self):
        for token in (
            "IMPULSE_2_4_PARALLEL_3",
            "ZIG_ZAG_0B_PARALLEL_A",
            "LOWER_DEGREE_W4_ZONE_0_25_ATR",
            "FIB_CHANNEL_CLUSTER",
            "FBO_BASE_CANDIDATE",
            "currentConfidence",
            "currentChannelTarget",
            '"EW FBD FBO CANDIDATE"',
            "channel24 = line.new",
            "channel3 = line.new",
            "zig0B = line.new",
        ):
            self.assertIn(token, self.source)
        self.assertNotIn('lastReasonCode := "FBO_BASE_CANDIDATE"', self.source)

    def test_v4_locked_nine_degree_router_and_parent_alignment_are_present(self):
        locked_routes = (
            ('"M"', "2", "routeMSourceOffset"),
            ('"W"', "3", "routeWSourceOffset"),
            ('"D"', "5", "routeDSourceOffset"),
            ('"288"', "5", "route288SourceOffset"),
            ('"240"', "5", "route240SourceOffset"),
            ('"60"', "7", "route60SourceOffset"),
            ('"15"', "9", "route15SourceOffset"),
            ('"5"', "12", "route5SourceOffset"),
            ('"3"', "15", "route3SourceOffset"),
        )
        for timeframe, pivot, source_offset in locked_routes:
            self.assertIn(
                f"request.security(syminfo.tickerid, {timeframe}, f_degree_route_snapshot({pivot}, {source_offset})",
                self.source,
            )
        self.assertGreaterEqual(self.source.count("barmerge.lookahead_on"), 11)
        self.assertIn("f_route_alignment_text(route60Dir, route240Dir, true)", self.source)
        self.assertIn("f_route_alignment_text(route60Dir, route288Dir, true)", self.source)
        self.assertIn("routeConfidenceBonus := routeParentAligned ? 5.0 : 0.0", self.source)
        self.assertIn("currentConfidence + routeConfidenceBonus", self.source)
        self.assertIn("routeMoves > 21", self.source)
        self.assertNotIn("routeMoves %", self.source)
        route_function = self.source.index("f_degree_route_snapshot")
        route_range = self.source.index("routeRange = ta.highest", route_function)
        route_condition = self.source.index("if routeType != 0", route_function)
        self.assertLess(route_range, route_condition)

    def test_v4_double_wxy_uses_locked_fib_time_and_post_y_confirmation(self):
        self.assertIn("f_eval_complex_correction", self.source)
        self.assertIn("xRatio >= 0.142 and xRatio <= 0.50", self.source)
        self.assertIn("xRatio >= 0.618 and xRatio <= 1.11", self.source)
        self.assertIn("yProjection >= 0.618", self.source)
        self.assertIn("f_double_post_y_confirmation", self.source)
        self.assertIn("WXY_38_2_RETRACE", self.source)
        self.assertIn("0-X_CLOSED_BREAK", self.source)
        self.assertIn("DOUBLE_CONFIRMATION_PENDING", self.source)
        self.assertIn("max_bars_back(close, 5000)", self.source)

    def test_v4_triple_uses_distinct_xx_component_and_terminal_z(self):
        self.assertIn('primary := "W-X-Y-XX-Z"', self.source)
        self.assertIn("xxRatio >= 0.50 and xxRatio <= 0.618", self.source)
        self.assertIn("xBoundaryPass", self.source)
        self.assertIn("f_near_duration(xxDuration, xDuration)", self.source)
        self.assertIn('reason := "TRIPLE_CONFIRMED"', self.source)
        self.assertIn('position == 3 ? "XX"', self.source)

    def test_v4_leading_and_ending_diagonals_are_position_locked(self):
        for token in (
            "f_eval_diagonal",
            'diagonalKind == "leading"',
            '"5-3-5-3-5"',
            '"3-3-3-3-3"',
            '"LEADING_DIAGONAL_"',
            '"ENDING_DIAGONAL_"',
            "wave2BoundaryPass",
            "leadingFibPass",
            "endingDivergence",
            'f_eval_diagonal(w4Index, latestIndex, "ending")',
            'f_eval_diagonal(bIndex, endIndex, "ending")',
        ):
            self.assertIn(token, self.source)
        self.assertNotIn('f_eval_diagonal(w2Index, latestIndex, "leading")', self.source)
        self.assertNotIn('f_eval_diagonal(w3Index, latestIndex, "ending")', self.source)

    def test_live_rendering_releases_undrawable_or_evicted_active_counts(self):
        for token in (
            "f_bar_drawable(candidateBar)",
            "candidateBar >= bar_index - 4999",
            "retentionInvalidated",
            '"ACTIVE_ENDPOINT_EVICTED"',
            "baseOutsideDegreeWindow",
            '"ACTIVE_DEGREE_WINDOW_EXPIRED"',
            "bar_index - lockedBaseBar > degreeWindowChartBars",
        ):
            self.assertIn(token, self.source)
        self.assertIn("if f_bar_drawable(lastInvalidBar)", self.source)

    def test_v4_c23_wave5_extension_has_instrument_gate(self):
        for token in (
            'instrumentType = input.string("Auto"',
            'syminfo.type == "index"',
            "allowIndexW5Extension",
            "extensionStructure",
            "extensionMarketAllowed",
            '"W5_EXTENSION"',
            '"W5_EXTENSION_INDEX_DISABLED"',
        ):
            self.assertIn(token, self.source)

    def test_wave5_is_archived_while_larger_correction_develops(self):
        self.assertIn("f_remove_history_cycle(cycleId)", self.source)
        self.assertIn(
            "f_archive_locked_cycle(completedCycleCount, motiveOldestCycleToKeep)",
            self.source,
        )
        self.assertIn("if not na(lockedABar)", self.source)

    def test_gue_support_layer_is_confidence_only(self):
        for token in (
            "bbDirectionalExpansion",
            "gmmaFast",
            "gmmaSlow",
            "volumeRatio",
            "atrAverage",
            '"BB_DIRECTIONAL_EXPANSION"',
            '"GMMA_TREND_ALIGNED"',
            '"VOLUME_HIGH"',
            '"VOLUME_DRY_UP"',
            '"VOLATILITY_DECREASE"',
            "currentConfidence := math.min(100.0, currentConfidence + gueSupportCount * 5.0)",
        ):
            self.assertIn(token, self.source)

    def test_client_gue_overlay_exposes_right_scale_values(self):
        for token in (
            'showGueOverlay = input.bool(true',
            'showGueBandFill = input.bool(true',
            '"BB Upper 20/2"',
            '"EMA 13"',
            '"EMA 26"',
            '"EMA 50"',
            '"EMA 60"',
            '"EMA 100"',
            '"BB Lower 20/2"',
            'title="BB Light Blue Fill"',
        ):
            self.assertIn(token, self.source)

    def test_client_fib_ladder_uses_previous_structure_and_readable_labels(self):
        for token in (
            "f_structural_fib_price(ratio)",
            "previousCycleEnd",
            "for fibIndex = 0 to 8",
            "extend=extend.both",
            "size=size.normal",
            "chart.right_visible_bar_time",
            "xloc=xloc.bar_time",
            "f_draw_anchor_fib(latestAnchor, structuralAllSwings)",
        ):
            self.assertIn(token, self.source)

    def test_searching_state_keeps_a_non_authoritative_structural_wave_map(self):
        for token in (
            'indicator("Elliott Wave Notes Overlay v4.2 Multi-Cycle"',
            'showSearchWaveMap = input.bool(true',
            'dashboardMode = input.string("Hidden"',
            'candidateState == "SEARCHING"',
            "completedCycleCount == 0",
            "if barstate.islast and f_is_candidate_mode() and showSearchWaveMap",
            "structuralAllSwings ? f_phase(i) : f_wave_phase(i)",
            "f_latest_context_anchor_index",
            "f_redraw(true, true, true, false)",
            "f_redraw(true, true, false, true)",
            "context only; they do not change or override the authoritative candidate state",
        ):
            self.assertIn(token, self.source)


if __name__ == "__main__":
    unittest.main()
