# -*- coding: utf-8 -*-
"""Safe action schema validation for game_reverse."""

SAFE_ACTIONS = {"screenshot", "wait", "back", "tap", "swipe", "hold_drag_release"}


def validate_action(action, allowed_actions, screen_size):
    if not isinstance(action, dict):
        raise ValueError("action must be an object")

    action_type = action.get("type")
    if action_type not in SAFE_ACTIONS:
        raise ValueError("action type is not allowed")
    if action_type not in allowed_actions:
        raise ValueError("action type is not allowed")

    width, height = screen_size

    if action_type == "screenshot":
        return {"type": "screenshot"}
    if action_type == "back":
        return {"type": "back"}
    if action_type == "wait":
        seconds = action.get("seconds", 1)
        if not isinstance(seconds, (int, float)) or seconds < 0 or seconds > 10:
            raise ValueError("wait seconds must be between 0 and 10")
        return {"type": "wait", "seconds": seconds}
    if action_type == "tap":
        x = action.get("x")
        y = action.get("y")
        _validate_point(x, y, width, height)
        return {"type": "tap", "x": x, "y": y}
    if action_type == "swipe":
        x1 = action.get("x1")
        y1 = action.get("y1")
        x2 = action.get("x2")
        y2 = action.get("y2")
        _validate_point(x1, y1, width, height)
        _validate_point(x2, y2, width, height)
        duration = action.get("duration", 0.5)
        if not isinstance(duration, (int, float)) or duration <= 0 or duration > 5:
            raise ValueError("swipe duration must be between 0 and 5")
        return {
            "type": "swipe",
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "duration": duration,
        }
    if action_type == "hold_drag_release":
        x1 = action.get("x1")
        y1 = action.get("y1")
        x2 = action.get("x2")
        y2 = action.get("y2")
        _validate_point(x1, y1, width, height)
        _validate_point(x2, y2, width, height)
        hold_seconds = action.get("hold_seconds", 0.3)
        if not isinstance(hold_seconds, (int, float)) or hold_seconds < 0 or hold_seconds > 5:
            raise ValueError("hold seconds must be between 0 and 5")
        duration = action.get("duration", 0.5)
        if not isinstance(duration, (int, float)) or duration <= 0 or duration > 5:
            raise ValueError("swipe duration must be between 0 and 5")
        return {
            "type": "hold_drag_release",
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "hold_seconds": hold_seconds,
            "duration": duration,
        }

    raise ValueError("unsupported action")


def _validate_point(x, y, width, height):
    if not isinstance(x, int) or not isinstance(y, int):
        raise ValueError("coordinates must be integers")
    if x < 0 or y < 0 or x >= width or y >= height:
        raise ValueError("coordinates out of bounds")
