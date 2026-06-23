# -*- coding: utf-8 -*-
"""Tests for continuous-control composite controllers."""

import json
import os
import tempfile
import unittest

from game_reverse.continuous_control import AimController
from game_reverse.journal import Journal


class RecordingPointerExecutor:
    def __init__(self, fail_on=None):
        self.pointer_commands = []
        self.executed = []
        self.fail_on = fail_on
        self.released = False

    def execute_pointer_command(self, command):
        self.pointer_commands.append(dict(command))
        if command["type"] == self.fail_on:
            raise RuntimeError("pointer failed")
        return "executed"

    def execute(self, action, screen_path):
        self.executed.append((dict(action), screen_path))
        if action["type"] == "screenshot":
            with open(screen_path, "wb") as screen_file:
                screen_file.write(("screen-%s" % len(self.executed)).encode("ascii"))
        return "executed"

    def release_active_pointer(self):
        self.released = True
        return True


class TestContinuousControl(unittest.TestCase):
    def test_aim_controller_holds_moves_relative_to_cursor_and_releases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, "control-session")
            executor = RecordingPointerExecutor()
            controller = AimController(executor, journal, screen_size=(1080, 1920))

            result = controller.execute(
                {
                    "type": "aim_fire",
                    "control": {"x": 450, "y": 1175, "role": "fire_button"},
                    "cursor": {"x": 500, "y": 800, "role": "crosshair"},
                    "target": {"x": 420, "y": 760, "role": "collectible"},
                    "hold_seconds": 0.4,
                    "max_adjustments": 2,
                },
                step=4,
            )

            with open(os.path.join(journal.session_dir, "control_sessions.jsonl"), encoding="utf-8") as events_file:
                events = [json.loads(line) for line in events_file if line.strip()]
            hold_screen_exists = os.path.exists(
                os.path.join(journal.session_dir, "screens", "control_step_0004_hold_01.png")
            )

        self.assertEqual(result["result"], "executed")
        self.assertEqual([command["type"] for command in executor.pointer_commands], ["touch_down", "touch_hold", "touch_move", "touch_up"])
        self.assertEqual(executor.pointer_commands[0], {"type": "touch_down", "x": 450, "y": 1175})
        self.assertEqual(executor.pointer_commands[2]["x"], 370)
        self.assertEqual(executor.pointer_commands[2]["y"], 1135)
        self.assertEqual(result["control_feedback"], "control_released_safely")
        self.assertTrue(any(event["phase"] == "adjust" for event in events))
        self.assertTrue(hold_screen_exists)

    def test_aim_controller_releases_pointer_when_move_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, "control-session")
            executor = RecordingPointerExecutor(fail_on="touch_move")
            controller = AimController(executor, journal, screen_size=(1080, 1920))

            with self.assertRaisesRegex(RuntimeError, "pointer failed"):
                controller.execute(
                    {
                        "type": "aim_fire",
                        "control": {"x": 450, "y": 1175},
                        "cursor": {"x": 500, "y": 800},
                        "target": {"x": 420, "y": 760},
                    },
                    step=1,
                )

        self.assertTrue(executor.released)


if __name__ == "__main__":
    unittest.main()
