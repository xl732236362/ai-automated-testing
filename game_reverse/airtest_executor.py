# -*- coding: utf-8 -*-
"""Airtest execution boundary for validated game_reverse actions."""


class AirtestExecutor:
    def __init__(self, api=None):
        self.api = api or _load_airtest_api()
        self.pointer_active = False
        self.pointer_position = None

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

    def execute_pointer_command(self, command):
        command_type = command["type"]
        if command_type == "touch_down":
            self._require_touch_api("touch_down")
            pos = (command["x"], command["y"])
            self.api.touch_down(pos)
            self.pointer_active = True
            self.pointer_position = pos
            return "executed"
        if command_type == "touch_move":
            self._require_touch_api("touch_move")
            pos = (command["x"], command["y"])
            self.api.touch_move(pos, duration=command.get("duration", 0.2))
            self.pointer_position = pos
            return "executed"
        if command_type == "touch_hold":
            self.api.sleep(command.get("seconds", 0.1))
            return "executed"
        if command_type == "touch_up":
            self._require_touch_api("touch_up")
            pos = None
            if "x" in command and "y" in command:
                pos = (command["x"], command["y"])
            elif self.pointer_position is not None:
                pos = self.pointer_position
            self.api.touch_up(pos)
            self.pointer_active = False
            self.pointer_position = None
            return "executed"
        raise ValueError("unsupported pointer command")

    def release_active_pointer(self):
        if not self.pointer_active:
            return False
        self._require_touch_api("touch_up")
        self.api.touch_up(self.pointer_position)
        self.pointer_active = False
        self.pointer_position = None
        return True

    def _hold_drag_release(self, action):
        start = (action["x1"], action["y1"])
        end = (action["x2"], action["y2"])
        hold_seconds = action.get("hold_seconds", 0.3)
        duration = action.get("duration", 0.5)

        if all(hasattr(self.api, name) for name in ("touch_down", "touch_move", "touch_up")):
            self.execute_pointer_command({"type": "touch_down", "x": start[0], "y": start[1]})
            try:
                self.execute_pointer_command({"type": "touch_hold", "seconds": hold_seconds})
                self.execute_pointer_command(
                    {
                        "type": "touch_move",
                        "x": end[0],
                        "y": end[1],
                        "duration": duration,
                    }
                )
            finally:
                self.execute_pointer_command({"type": "touch_up", "x": end[0], "y": end[1]})
            return

        self.api.swipe(start, end, duration=hold_seconds + duration)

    def _require_touch_api(self, name):
        if not hasattr(self.api, name):
            raise RuntimeError("%s is required for internal pointer commands" % name)


def _load_airtest_api():
    from airtest.core import api as airtest_api

    return airtest_api
