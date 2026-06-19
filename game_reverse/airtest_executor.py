# -*- coding: utf-8 -*-
"""Airtest execution boundary for validated game_reverse actions."""


class AirtestExecutor:
    def __init__(self, api=None):
        self.api = api or _load_airtest_api()

    def connect(self, device_uri):
        return self.api.connect_device(device_uri)

    def start_app(self, package_name):
        return self.api.start_app(package_name)

    def execute(self, action, screen_path):
        action_type = action["type"]
        if action_type == "screenshot":
            self.api.snapshot(filename=screen_path)
            return "executed"
        if action_type == "tap":
            self.api.touch((action["x"], action["y"]))
            return "executed"
        if action_type == "swipe":
            self.api.swipe(
                (action["x1"], action["y1"]),
                (action["x2"], action["y2"]),
                duration=action.get("duration", 0.5),
            )
            return "executed"
        if action_type == "hold_drag_release":
            self._hold_drag_release(action)
            return "executed"
        if action_type == "back":
            self.api.keyevent("BACK")
            return "executed"
        if action_type == "wait":
            self.api.sleep(action.get("seconds", 1))
            return "executed"
        raise ValueError("unsupported action")

    def _hold_drag_release(self, action):
        start = (action["x1"], action["y1"])
        end = (action["x2"], action["y2"])
        hold_seconds = action.get("hold_seconds", 0.3)
        duration = action.get("duration", 0.5)

        if all(hasattr(self.api, name) for name in ("touch_down", "touch_move", "touch_up")):
            self.api.touch_down(start)
            try:
                self.api.sleep(hold_seconds)
                self.api.touch_move(end, duration=duration)
            finally:
                self.api.touch_up(end)
            return

        self.api.swipe(start, end, duration=hold_seconds + duration)


def _load_airtest_api():
    from airtest.core import api as airtest_api

    return airtest_api
