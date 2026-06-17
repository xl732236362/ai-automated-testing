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


if __name__ == "__main__":
    unittest.main()
