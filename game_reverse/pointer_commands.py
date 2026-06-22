# -*- coding: utf-8 -*-
"""Internal pointer command validation for continuous-control controllers."""

POINTER_COMMANDS = {"touch_down", "touch_move", "touch_hold", "touch_up"}


def validate_pointer_command(command, screen_size):
    if not isinstance(command, dict):
        raise ValueError("pointer command must be an object")

    command_type = command.get("type")
    if command_type not in POINTER_COMMANDS:
        raise ValueError("pointer command type is not allowed")

    width, height = screen_size
    if command_type in ("touch_down", "touch_move"):
        x = command.get("x")
        y = command.get("y")
        _validate_point(x, y, width, height)
        if command_type == "touch_down":
            return {"type": "touch_down", "x": x, "y": y}
        duration = command.get("duration", 0.2)
        _validate_duration(duration)
        return {"type": "touch_move", "x": x, "y": y, "duration": duration}

    if command_type == "touch_hold":
        seconds = command.get("seconds", 0.1)
        if not isinstance(seconds, (int, float)) or seconds < 0 or seconds > 5:
            raise ValueError("hold seconds must be between 0 and 5")
        return {"type": "touch_hold", "seconds": seconds}

    if command_type == "touch_up":
        if "x" not in command and "y" not in command:
            return {"type": "touch_up"}
        x = command.get("x")
        y = command.get("y")
        _validate_point(x, y, width, height)
        return {"type": "touch_up", "x": x, "y": y}

    raise ValueError("unsupported pointer command")


def _validate_point(x, y, width, height):
    if not isinstance(x, int) or not isinstance(y, int):
        raise ValueError("coordinates must be integers")
    if x < 0 or y < 0 or x >= width or y >= height:
        raise ValueError("coordinates out of bounds")


def _validate_duration(duration):
    if not isinstance(duration, (int, float)) or duration <= 0 or duration > 5:
        raise ValueError("duration must be between 0 and 5")
