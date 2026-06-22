# -*- coding: utf-8 -*-
"""Tests for internal continuous-control pointer command validation."""

import unittest

from game_reverse.pointer_commands import validate_pointer_command


class TestPointerCommands(unittest.TestCase):
    def test_accepts_touch_down_command(self):
        command = validate_pointer_command({"type": "touch_down", "x": 10, "y": 20}, (1080, 1920))

        self.assertEqual(command, {"type": "touch_down", "x": 10, "y": 20})

    def test_accepts_touch_move_with_duration(self):
        command = validate_pointer_command(
            {"type": "touch_move", "x": 100, "y": 200, "duration": 0.25},
            (1080, 1920),
        )

        self.assertEqual(command, {"type": "touch_move", "x": 100, "y": 200, "duration": 0.25})

    def test_accepts_touch_hold_with_seconds(self):
        command = validate_pointer_command({"type": "touch_hold", "seconds": 0.4}, (1080, 1920))

        self.assertEqual(command, {"type": "touch_hold", "seconds": 0.4})

    def test_accepts_touch_up_with_position(self):
        command = validate_pointer_command({"type": "touch_up", "x": 100, "y": 200}, (1080, 1920))

        self.assertEqual(command, {"type": "touch_up", "x": 100, "y": 200})

    def test_accepts_touch_up_without_position(self):
        command = validate_pointer_command({"type": "touch_up"}, (1080, 1920))

        self.assertEqual(command, {"type": "touch_up"})

    def test_rejects_out_of_bounds_pointer_position(self):
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            validate_pointer_command({"type": "touch_down", "x": 2000, "y": 20}, (1080, 1920))

    def test_rejects_invalid_duration(self):
        with self.assertRaisesRegex(ValueError, "duration"):
            validate_pointer_command({"type": "touch_move", "x": 100, "y": 200, "duration": 0}, (1080, 1920))

    def test_rejects_invalid_hold_seconds(self):
        with self.assertRaisesRegex(ValueError, "hold seconds"):
            validate_pointer_command({"type": "touch_hold", "seconds": 6}, (1080, 1920))

    def test_rejects_unknown_pointer_command(self):
        with self.assertRaisesRegex(ValueError, "pointer command"):
            validate_pointer_command({"type": "tap", "x": 10, "y": 20}, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
