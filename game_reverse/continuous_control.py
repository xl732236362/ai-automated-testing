# -*- coding: utf-8 -*-
"""Composite continuous-control controllers built on internal pointer commands."""

import os

from game_reverse.pointer_commands import validate_pointer_command


class AimController:
    """Hold a fire control, adjust aim from cursor toward target, then release."""

    def __init__(self, executor, journal, screen_size, move_duration=0.25):
        self.executor = executor
        self.journal = journal
        self.screen_size = screen_size
        self.move_duration = move_duration

    def execute(self, action, step):
        events = []
        control = action["control"]
        cursor = action.get("cursor") or action["target"]
        target = action["target"]
        max_adjustments = action.get("max_adjustments", 3)
        final_point = _bounded_point(
            control["x"] + (target["x"] - cursor["x"]),
            control["y"] + (target["y"] - cursor["y"]),
            self.screen_size,
        )

        try:
            self._pointer({"type": "touch_down", "x": control["x"], "y": control["y"]})
            events.append(self._capture_event(step, "hold", 1, {"command": "touch_down"}))
            self._pointer({"type": "touch_hold", "seconds": action.get("hold_seconds", 0.3)})
            events.append(self._capture_event(step, "hold", 2, {"command": "touch_hold"}))

            if max_adjustments > 0:
                self._pointer(
                    {
                        "type": "touch_move",
                        "x": final_point["x"],
                        "y": final_point["y"],
                        "duration": self.move_duration,
                    }
                )
                events.append(
                    self._capture_event(
                        step,
                        "adjust",
                        1,
                        {
                            "command": "touch_move",
                            "from_cursor": cursor,
                            "target": target,
                            "pointer": final_point,
                        },
                    )
                )
        except Exception:
            release = getattr(self.executor, "release_active_pointer", None)
            if release is not None:
                release()
            raise

        self._pointer({"type": "touch_up", "x": final_point["x"], "y": final_point["y"]})
        events.append(self._capture_event(step, "release", 1, {"command": "touch_up"}))
        return {
            "result": "executed",
            "control_events": events,
            "control_feedback": "control_released_safely",
        }

    def _pointer(self, command):
        command = validate_pointer_command(command, self.screen_size)
        return self.executor.execute_pointer_command(command)

    def _capture_event(self, step, phase, index, extra):
        screen_path = self.journal.control_screen_path(step, phase, index)
        self.executor.execute({"type": "screenshot"}, screen_path)
        event = {
            "step": step,
            "phase": phase,
            "index": index,
            "screen": os.path.relpath(screen_path, self.journal.session_dir),
            "result": "captured",
        }
        event.update(extra)
        self.journal.write_control_event(event)
        return event


def _bounded_point(x, y, screen_size):
    width, height = screen_size
    return {
        "x": max(0, min(width - 1, int(round(x)))),
        "y": max(0, min(height - 1, int(round(y)))),
    }
