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


if __name__ == "__main__":
    unittest.main()
