# -*- coding: utf-8 -*-
"""Tests for game_reverse Airtest executor wrapper."""

import unittest

from game_reverse.airtest_executor import AirtestExecutor


class FakeApi:
    def __init__(self):
        self.calls = []

    def snapshot(self, filename=None):
        self.calls.append(("snapshot", filename))
        return filename

    def touch(self, pos):
        self.calls.append(("touch", pos))

    def swipe(self, start, end, duration=0.5):
        self.calls.append(("swipe", start, end, duration))

    def keyevent(self, key):
        self.calls.append(("keyevent", key))

    def sleep(self, seconds):
        self.calls.append(("sleep", seconds))


class FakeGestureApi(FakeApi):
    def touch_down(self, pos):
        self.calls.append(("touch_down", pos))

    def touch_move(self, pos, duration=0.5):
        self.calls.append(("touch_move", pos, duration))

    def touch_up(self, pos=None):
        self.calls.append(("touch_up", pos))


class FailingMoveGestureApi(FakeGestureApi):
    def __init__(self):
        super().__init__()
        self.executor = None
        self.pointer_active_on_touch_up = None

    def touch_move(self, pos, duration=0.5):
        self.calls.append(("touch_move", pos, duration))
        raise RuntimeError("move failed")

    def touch_up(self, pos=None):
        if self.executor is not None:
            self.pointer_active_on_touch_up = self.executor.pointer_active
        super().touch_up(pos)


class TestAirtestExecutor(unittest.TestCase):
    def test_executes_screenshot(self):
        api = FakeApi()
        executor = AirtestExecutor(api=api)

        executor.execute({"type": "screenshot"}, screen_path="screen.png")

        self.assertEqual(api.calls, [("snapshot", "screen.png")])

    def test_executes_tap(self):
        api = FakeApi()
        executor = AirtestExecutor(api=api)

        executor.execute({"type": "tap", "x": 10, "y": 20}, screen_path="screen.png")

        self.assertEqual(api.calls, [("touch", (10, 20))])

    def test_executes_back(self):
        api = FakeApi()
        executor = AirtestExecutor(api=api)

        executor.execute({"type": "back"}, screen_path="screen.png")

        self.assertEqual(api.calls, [("keyevent", "BACK")])

    def test_executes_hold_drag_release_as_press_wait_drag_release(self):
        api = FakeGestureApi()
        executor = AirtestExecutor(api=api)

        executor.execute(
            {
                "type": "hold_drag_release",
                "x1": 450,
                "y1": 1200,
                "x2": 520,
                "y2": 820,
                "hold_seconds": 0.4,
                "duration": 1.2,
            },
            screen_path="screen.png",
        )

        self.assertEqual(
            api.calls,
            [
                ("touch_down", (450, 1200)),
                ("sleep", 0.4),
                ("touch_move", (520, 820), 1.2),
                ("touch_up", (520, 820)),
            ],
        )

    def test_executes_internal_pointer_commands_and_tracks_active_pointer(self):
        api = FakeGestureApi()
        executor = AirtestExecutor(api=api)

        executor.execute_pointer_command({"type": "touch_down", "x": 10, "y": 20})
        executor.execute_pointer_command({"type": "touch_hold", "seconds": 0.2})
        executor.execute_pointer_command({"type": "touch_move", "x": 30, "y": 40, "duration": 0.3})
        executor.execute_pointer_command({"type": "touch_up", "x": 30, "y": 40})

        self.assertEqual(
            api.calls,
            [
                ("touch_down", (10, 20)),
                ("sleep", 0.2),
                ("touch_move", (30, 40), 0.3),
                ("touch_up", (30, 40)),
            ],
        )
        self.assertFalse(executor.pointer_active)

    def test_release_active_pointer_releases_last_position_once(self):
        api = FakeGestureApi()
        executor = AirtestExecutor(api=api)

        executor.execute_pointer_command({"type": "touch_down", "x": 10, "y": 20})
        executor.execute_pointer_command({"type": "touch_move", "x": 30, "y": 40, "duration": 0.3})
        released = executor.release_active_pointer()
        released_again = executor.release_active_pointer()

        self.assertTrue(released)
        self.assertFalse(released_again)
        self.assertEqual(api.calls[-1], ("touch_up", (30, 40)))
        self.assertFalse(executor.pointer_active)

    def test_pointer_command_requires_touch_api(self):
        api = FakeApi()
        executor = AirtestExecutor(api=api)

        with self.assertRaisesRegex(RuntimeError, "touch_down"):
            executor.execute_pointer_command({"type": "touch_down", "x": 10, "y": 20})

    def test_hold_drag_release_clears_pointer_state_when_move_fails(self):
        api = FailingMoveGestureApi()
        executor = AirtestExecutor(api=api)
        api.executor = executor

        with self.assertRaisesRegex(RuntimeError, "move failed"):
            executor.execute(
                {
                    "type": "hold_drag_release",
                    "x1": 450,
                    "y1": 1200,
                    "x2": 520,
                    "y2": 820,
                    "hold_seconds": 0.4,
                    "duration": 1.2,
                },
                screen_path="screen.png",
            )

        self.assertEqual(api.calls[-1], ("touch_up", (520, 820)))
        self.assertTrue(api.pointer_active_on_touch_up)
        self.assertFalse(executor.pointer_active)


if __name__ == "__main__":
    unittest.main()
