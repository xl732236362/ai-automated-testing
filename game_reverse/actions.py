# -*- coding: utf-8 -*-
"""Safe action schema validation for game_reverse."""

SAFE_ACTIONS = {
    "screenshot",
    "wait",
    "back",
    "tap",
    "swipe",
    "hold_drag_release",
    "tap_target",
    "swipe_target",
    "hold_drag_target",
}

SWIPE_DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


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
    if action_type == "tap_target":
        target = _validate_target(action, "target", width, height)
        x, y = _bounds_center(target["bounds"])
        resolved = {"type": "tap", "x": x, "y": y, "target": target}
        _copy_optional_fields(resolved, action, ("target_ref",))
        return resolved
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
    if action_type == "swipe_target":
        target = _validate_target(action, "target", width, height)
        x1, y1 = _bounds_center(target["bounds"])
        direction = action.get("direction")
        if direction not in SWIPE_DIRECTIONS:
            raise ValueError("swipe direction must be up, down, left, or right")
        distance = action.get("distance", min(width, height) // 5)
        if not isinstance(distance, int) or distance <= 0 or distance > max(width, height):
            raise ValueError("swipe distance must be a positive integer within the screen")
        dx, dy = SWIPE_DIRECTIONS[direction]
        x2 = x1 + (dx * distance)
        y2 = y1 + (dy * distance)
        _validate_point(x2, y2, width, height)
        duration = action.get("duration", 0.5)
        if not isinstance(duration, (int, float)) or duration <= 0 or duration > 5:
            raise ValueError("swipe duration must be between 0 and 5")
        resolved = {
            "type": "swipe",
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "duration": duration,
            "target": target,
        }
        _copy_optional_fields(resolved, action, ("target_ref",))
        return resolved
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
    if action_type == "hold_drag_target":
        source = _validate_target(action, "source", width, height)
        target = _validate_target(action, "target", width, height)
        x1, y1 = _bounds_center(source["bounds"])
        x2, y2 = _bounds_center(target["bounds"])
        hold_seconds = action.get("hold_seconds", 0.3)
        if not isinstance(hold_seconds, (int, float)) or hold_seconds < 0 or hold_seconds > 5:
            raise ValueError("hold seconds must be between 0 and 5")
        duration = action.get("duration", 0.5)
        if not isinstance(duration, (int, float)) or duration <= 0 or duration > 5:
            raise ValueError("swipe duration must be between 0 and 5")
        resolved = {
            "type": "hold_drag_release",
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "hold_seconds": hold_seconds,
            "duration": duration,
            "source": source,
            "target": target,
        }
        _copy_optional_fields(resolved, action, ("source_ref", "target_ref"))
        return resolved

    raise ValueError("unsupported action")


def _validate_point(x, y, width, height):
    if not isinstance(x, int) or not isinstance(y, int):
        raise ValueError("coordinates must be integers")
    if x < 0 or y < 0 or x >= width or y >= height:
        raise ValueError("coordinates out of bounds")


def _validate_target(action, field_name, width, height):
    target = action.get(field_name)
    if not isinstance(target, dict):
        raise ValueError("%s must be an object" % field_name)
    bounds = target.get("bounds")
    _validate_bounds(bounds, width, height, "%s bounds" % field_name)
    return target


def _validate_bounds(bounds, width, height, label):
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError("%s must be [left, top, right, bottom]" % label)
    if not all(isinstance(value, int) for value in bounds):
        raise ValueError("%s must contain integer coordinates" % label)
    left, top, right, bottom = bounds
    if left < 0 or top < 0 or right > width or bottom > height or left >= right or top >= bottom:
        raise ValueError("%s out of bounds" % label)


def _bounds_center(bounds):
    left, top, right, bottom = bounds
    return (left + right) // 2, (top + bottom) // 2


def _copy_optional_fields(destination, source, fields):
    for field in fields:
        if field in source:
            destination[field] = source[field]
