# -*- coding: utf-8 -*-
"""Tests for gameplay feedback classification."""

import unittest

from game_reverse.feedback import classify_feedback, recommend_next_strategy


class TestGameReverseFeedback(unittest.TestCase):
    def test_classifies_counter_change_from_observation_summary(self):
        feedback = classify_feedback(
            before={"screen_summary": "milk counter 3 and tray empty"},
            after={"screen_summary": "milk counter changed from 3 to 2 and tray has milk"},
        )

        self.assertEqual(feedback["result"], "counter_changed")
        self.assertIn("counter", feedback["evidence"])

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

    def test_recommends_switching_gesture_after_repeated_misses(self):
        strategy = recommend_next_strategy(
            [
                {"result": "no_visible_change", "action_type": "tap"},
                {"result": "no_visible_change", "action_type": "tap"},
            ]
        )

        self.assertEqual(strategy["next_strategy"], "switch_gesture")
        self.assertIn("hold_drag_release", strategy["recommended_actions"])


if __name__ == "__main__":
    unittest.main()
