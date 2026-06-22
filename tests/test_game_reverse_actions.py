# -*- coding: utf-8 -*-
"""Tests for game_reverse safe action validation."""

import unittest

from game_reverse.actions import validate_action


class TestGameReverseActions(unittest.TestCase):
    def test_accepts_wait_action(self):
        action = validate_action({"type": "wait", "seconds": 2}, ["wait"], (1080, 1920))

        self.assertEqual(action["type"], "wait")
        self.assertEqual(action["seconds"], 2)

    def test_accepts_tap_inside_screen(self):
        action = validate_action({"type": "tap", "x": 100, "y": 200}, ["tap"], (1080, 1920))

        self.assertEqual(action, {"type": "tap", "x": 100, "y": 200})

    def test_resolves_tap_target_to_center_tap(self):
        action = validate_action(
            {
                "type": "tap_target",
                "target": {
                    "kind": "ocr",
                    "text": "Start",
                    "bounds": [100, 200, 220, 260],
                },
                "target_ref": "start_button",
            },
            ["tap_target"],
            (1080, 1920),
        )

        self.assertEqual(
            action,
            {
                "type": "tap",
                "x": 160,
                "y": 230,
                "target_ref": "start_button",
                "target": {
                    "kind": "ocr",
                    "text": "Start",
                    "bounds": [100, 200, 220, 260],
                },
            },
        )

    def test_resolves_swipe_target_to_region_swipe(self):
        action = validate_action(
            {
                "type": "swipe_target",
                "target": {"bounds": [100, 200, 300, 500]},
                "direction": "up",
                "distance": 120,
                "duration": 0.7,
            },
            ["swipe_target"],
            (1080, 1920),
        )

        self.assertEqual(
            action,
            {
                "type": "swipe",
                "x1": 200,
                "y1": 350,
                "x2": 200,
                "y2": 230,
                "duration": 0.7,
                "target": {"bounds": [100, 200, 300, 500]},
            },
        )

    def test_resolves_hold_drag_target_between_regions(self):
        action = validate_action(
            {
                "type": "hold_drag_target",
                "source": {"bounds": [100, 200, 200, 300]},
                "target": {"bounds": [400, 700, 500, 900]},
                "hold_seconds": 0.4,
                "duration": 1.1,
            },
            ["hold_drag_target"],
            (1080, 1920),
        )

        self.assertEqual(
            action,
            {
                "type": "hold_drag_release",
                "x1": 150,
                "y1": 250,
                "x2": 450,
                "y2": 800,
                "hold_seconds": 0.4,
                "duration": 1.1,
                "source": {"bounds": [100, 200, 200, 300]},
                "target": {"bounds": [400, 700, 500, 900]},
            },
        )

    def test_rejects_target_outside_screen(self):
        with self.assertRaisesRegex(ValueError, "target bounds"):
            validate_action(
                {"type": "tap_target", "target": {"bounds": [100, 200, 2000, 300]}},
                ["tap_target"],
                (1080, 1920),
            )

    def test_rejects_disallowed_action(self):
        with self.assertRaisesRegex(ValueError, "not allowed"):
            validate_action({"type": "shell", "cmd": "pm clear app"}, ["tap"], (1080, 1920))

    def test_rejects_out_of_bounds_tap(self):
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            validate_action({"type": "tap", "x": 2000, "y": 200}, ["tap"], (1080, 1920))

    def test_rejects_swipe_with_out_of_bounds_point(self):
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            validate_action(
                {
                    "type": "swipe",
                    "x1": 100,
                    "y1": 200,
                    "x2": 100,
                    "y2": 3000,
                    "duration": 0.5,
                },
                ["swipe"],
                (1080, 1920),
            )

    def test_accepts_hold_drag_release_action(self):
        action = validate_action(
            {
                "type": "hold_drag_release",
                "x1": 450,
                "y1": 1200,
                "x2": 520,
                "y2": 820,
                "hold_seconds": 0.4,
                "duration": 1.2,
            },
            ["hold_drag_release"],
            (1080, 1920),
        )

        self.assertEqual(
            action,
            {
                "type": "hold_drag_release",
                "x1": 450,
                "y1": 1200,
                "x2": 520,
                "y2": 820,
                "hold_seconds": 0.4,
                "duration": 1.2,
            },
        )

    def test_rejects_hold_drag_release_with_invalid_hold_seconds(self):
        with self.assertRaisesRegex(ValueError, "hold seconds"):
            validate_action(
                {
                    "type": "hold_drag_release",
                    "x1": 450,
                    "y1": 1200,
                    "x2": 520,
                    "y2": 820,
                    "hold_seconds": 6,
                    "duration": 1.2,
                },
                ["hold_drag_release"],
                (1080, 1920),
            )

    def test_rejects_raw_pointer_commands_as_public_actions(self):
        for action_type in ("touch_down", "touch_move", "touch_hold", "touch_up"):
            with self.subTest(action_type=action_type):
                with self.assertRaisesRegex(ValueError, "not allowed"):
                    validate_action(
                        {"type": action_type, "x": 10, "y": 20, "seconds": 0.1},
                        [action_type],
                        (1080, 1920),
                    )


if __name__ == "__main__":
    unittest.main()
