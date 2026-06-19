# -*- coding: utf-8 -*-
"""Tests for affordance discovery and feedback tracking."""

import unittest

from game_reverse.affordances import AffordanceMemory


class TestAffordanceMemory(unittest.TestCase):
    def test_collects_and_deduplicates_regions_from_observation_sources(self):
        memory = AffordanceMemory()

        collected = memory.collect_from_observation(
            "state_home",
            {
                "ocr": [{"text": "Start", "bounds": [100, 200, 220, 260]}],
                "ui_nodes": [{"text": "Start", "class": "Button", "bounds": [102, 201, 222, 261]}],
                "visual_regions": [{"bounds": [500, 900, 700, 1050], "reason": "large button"}],
                "proposed_regions": [{"bounds": [100, 200, 220, 260], "label": "start button"}],
            },
            screen_size=(1080, 1920),
        )

        self.assertEqual(len(collected), 2)
        labels = sorted(item["label"] for item in collected)
        self.assertEqual(labels, ["Start", "large button"])
        self.assertTrue(all(item["state_id"] == "state_home" for item in collected))
        self.assertTrue(all(item["supported_actions"] for item in collected))

    def test_rejects_invalid_or_out_of_bounds_regions(self):
        memory = AffordanceMemory()

        collected = memory.collect_from_observation(
            "state_home",
            {
                "ocr": [
                    {"text": "Bad", "bounds": [-1, 10, 20, 40]},
                    {"text": "Also bad", "bounds": [10, 10, 10, 40]},
                    {"text": "Good", "bounds": [10, 10, 100, 40]},
                ]
            },
            screen_size=(200, 100),
        )

        self.assertEqual([item["label"] for item in collected], ["Good"])

    def test_records_no_change_feedback_for_tapped_region(self):
        memory = AffordanceMemory()
        memory.collect_from_observation(
            "state_home",
            {"ocr": [{"text": "Start", "bounds": [100, 200, 220, 260]}]},
            screen_size=(1080, 1920),
        )

        updated = memory.record_action_feedback(
            "state_home",
            {"type": "tap", "x": 150, "y": 230},
            "no_visible_change",
        )
        affordances = memory.to_affordances()["states"]["state_home"]

        self.assertEqual(len(updated), 1)
        self.assertEqual(affordances[0]["tested_count"], 1)
        self.assertEqual(affordances[0]["last_result"], "no_visible_change")
        self.assertEqual(affordances[0]["status"], "deprioritized")


if __name__ == "__main__":
    unittest.main()
