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


if __name__ == "__main__":
    unittest.main()
