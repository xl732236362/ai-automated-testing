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
        if action_type == "back":
            self.api.keyevent("BACK")
            return "executed"
        if action_type == "wait":
            self.api.sleep(action.get("seconds", 1))
            return "executed"
        raise ValueError("unsupported action")


def _load_airtest_api():
    from airtest.core import api as airtest_api

    return airtest_api
