# -*- coding: utf-8 -*-
"""Tests for gameplay feedback classification."""

import os
import tempfile
import unittest

from game_reverse.feedback import classify_feedback, derive_control_feedback, recommend_next_strategy


class TestGameReverseFeedback(unittest.TestCase):
    def test_classifies_counter_change_from_observation_summary(self):
        feedback = classify_feedback(
            before={"screen_summary": "milk counter 3 and tray empty"},
            after={"screen_summary": "milk counter changed from 3 to 2 and tray has milk"},
        )

        self.assertEqual(feedback["result"], "counter_changed")
        self.assertIn("counter", feedback["evidence"])

    def test_verified_progress_overrides_counter_keywords_when_counts_do_not_change(self):
        feedback = classify_feedback(
            before={"screen_summary": "target counters are visible"},
            after={
                "screen_summary": "target counters are visible and the crosshair moved",
                "verified_progress": {
                    "before_counts": [3, 3, 3, 6, 3, 3],
                    "after_counts": [3, 3, 3, 6, 3, 3],
                    "progress_delta": 0,
                    "changed": False,
                },
            },
        )

        self.assertEqual(feedback["result"], "visual_changed")
        self.assertEqual(feedback["progress_delta"], 0)

    def test_verified_progress_classifies_counter_change_only_when_counts_decrease(self):
        feedback = classify_feedback(
            before={"screen_summary": "target counters are visible"},
            after={
                "screen_summary": "target counters are visible",
                "verified_progress": {
                    "before_counts": [3, 3, 3, 6, 3, 3],
                    "after_counts": [3, 3, 2, 6, 3, 3],
                    "progress_delta": 1,
                    "changed": True,
                },
            },
        )

        self.assertEqual(feedback["result"], "counter_changed")
        self.assertEqual(feedback["progress_delta"], 1)

    def test_classifies_tray_change_without_counter_text(self):
        feedback = classify_feedback(
            before={"screen_summary": "bottom tray empty"},
            after={"screen_summary": "bottom tray now contains one rolling pin"},
        )

        self.assertEqual(feedback["result"], "tray_changed")

    def test_classifies_no_visible_change(self):
        feedback = classify_feedback(
            before={"screen_summary": "same stable screen"},
            after={"screen_summary": "same stable screen"},
        )

        self.assertEqual(feedback["result"], "no_visible_change")

    def test_classifies_visual_change_from_screenshot_hash(self):
        feedback = classify_feedback(
            before={"screen_summary": "menu", "screenshot_hash": "sha256:one"},
            after={"screen_summary": "menu", "screenshot_hash": "sha256:two"},
        )

        self.assertEqual(feedback["result"], "visual_changed")
        self.assertGreater(feedback["visual_diff_score"], 0)
        self.assertEqual(feedback["confidence"], "medium")

    def test_prefers_explicit_screenshot_paths_for_action_boundary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            before_path = os.path.join(tmpdir, "before.png")
            after_path = os.path.join(tmpdir, "after.png")
            with open(before_path, "wb") as before_file:
                before_file.write(b"same screen")
            with open(after_path, "wb") as after_file:
                after_file.write(b"same screen")

            feedback = classify_feedback(
                before={"screen_summary": "previous screen", "screenshot_hash": "sha256:old"},
                after={"screen_summary": "milk counter changed from 3 to 2", "screenshot_hash": "sha256:new"},
                before_screen_path=before_path,
                after_screen_path=after_path,
            )

        self.assertEqual(feedback["result"], "no_visible_change")
        self.assertEqual(feedback["visual_diff_score"], 0.0)

    def test_classifies_ocr_and_ui_changes(self):
        feedback = classify_feedback(
            before={
                "screen_summary": "menu",
                "ocr": [{"text": "Start"}],
                "ui_nodes": [{"text": "Start", "class": "Button"}],
            },
            after={
                "screen_summary": "menu",
                "ocr": [{"text": "Continue"}],
                "ui_nodes": [{"text": "Continue", "class": "Button"}],
            },
        )

        self.assertEqual(feedback["result"], "ocr_changed")
        self.assertTrue(feedback["ocr_changed"])
        self.assertTrue(feedback["ui_changed"])

    def test_classifies_sensitive_screen(self):
        feedback = classify_feedback(
            before={"screen_summary": "main menu"},
            after={"screen_summary": "Login required before payment or account access"},
        )

        self.assertEqual(feedback["result"], "sensitive_screen")
        self.assertEqual(feedback["safety_label"], "sensitive")
        self.assertEqual(feedback["confidence"], "high")

    def test_classifies_popup_result_and_failure_states(self):
        popup = classify_feedback(after={"screen_summary": "A modal popup dialog is open"})
        completed = classify_feedback(after={"screen_summary": "Level completed victory reward screen"})
        failed = classify_feedback(after={"screen_summary": "Level failed retry screen"})

        self.assertEqual(popup["result"], "popup_opened")
        self.assertEqual(completed["result"], "level_completed")
        self.assertEqual(failed["result"], "level_failed")

    def test_recommends_switching_gesture_after_repeated_misses(self):
        strategy = recommend_next_strategy(
            [
                {"result": "no_visible_change", "action_type": "tap"},
                {"result": "no_visible_change", "action_type": "tap"},
            ]
        )

        self.assertEqual(strategy["next_strategy"], "switch_gesture")
        self.assertIn("hold_drag_release", strategy["recommended_actions"])

    def test_recommends_recovery_for_sensitive_failure_and_loops(self):
        sensitive = recommend_next_strategy([{"result": "sensitive_screen"}])
        failure = recommend_next_strategy([{"result": "level_failed"}])
        loop = recommend_next_strategy(
            [
                {"result": "no_visible_change", "state_id": "state_a", "action_type": "tap"},
                {"result": "no_visible_change", "state_id": "state_a", "action_type": "tap"},
                {"result": "no_visible_change", "state_id": "state_a", "action_type": "tap"},
            ]
        )

        self.assertEqual(sensitive["next_strategy"], "back_or_wait_only")
        self.assertEqual(failure["next_strategy"], "recover_from_failure")
        self.assertEqual(loop["next_strategy"], "switch_target")
        self.assertIn("loop", loop["reason"])

    def test_derives_target_collected_for_successful_aim_fire(self):
        control_feedback = derive_control_feedback(
            {"type": "aim_fire"},
            {"result": "counter_changed", "progress_delta": 1},
        )

        self.assertEqual(control_feedback, "target_collected")

    def test_derives_control_attempt_failed_for_repeated_no_change_aim_fire(self):
        control_feedback = derive_control_feedback(
            {"type": "aim_fire"},
            {"result": "no_visible_change"},
            recent_feedback=[
                {"result": "no_visible_change", "action_type": "aim_fire"},
                {"result": "no_visible_change", "action_type": "aim_fire"},
            ],
        )

        self.assertEqual(control_feedback, "control_attempt_failed")


if __name__ == "__main__":
    unittest.main()
