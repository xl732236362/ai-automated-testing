# Continuous Control Phase 1 Pointer Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add internal pointer primitives for future continuous-control controllers while keeping raw `touch_*` commands unavailable to the LLM/Web public action surface.

**Architecture:** Public gameplay actions still flow through `game_reverse.actions.validate_action`. Internal continuous-control commands use a new focused validator in `game_reverse.pointer_commands`, and `AirtestExecutor` exposes explicit primitive execution methods plus a best-effort release cleanup hook. Existing `tap`, `swipe`, and `hold_drag_release` behavior remains compatible.

**Tech Stack:** Python `unittest`, existing `game_reverse` modules, Airtest API wrapper.

---

## File Structure

- Create `game_reverse/pointer_commands.py`: internal-only pointer command validation for `touch_down`, `touch_move`, `touch_hold`, and `touch_up`.
- Modify `game_reverse/airtest_executor.py`: add `execute_pointer_command`, pointer state tracking, and `release_active_pointer`.
- Modify `tests/test_game_reverse_actions.py`: prove public action validation rejects raw pointer commands.
- Create `tests/test_game_reverse_pointer_commands.py`: prove internal pointer command validation accepts valid commands and rejects invalid ones.
- Modify `tests/test_game_reverse_airtest_executor.py`: prove primitive execution order, active pointer tracking, cleanup, and existing hold-drag behavior.

## Task 1: Public Action Boundary Rejects Raw Pointer Commands

**Files:**
- Modify: `tests/test_game_reverse_actions.py`

- [ ] **Step 1: Write the failing boundary test**

Append this test method inside `TestGameReverseActions`:

```python
    def test_rejects_raw_pointer_commands_as_public_actions(self):
        for action_type in ("touch_down", "touch_move", "touch_hold", "touch_up"):
            with self.subTest(action_type=action_type):
                with self.assertRaisesRegex(ValueError, "not allowed"):
                    validate_action(
                        {"type": action_type, "x": 10, "y": 20, "seconds": 0.1},
                        [action_type],
                        (1080, 1920),
                    )
```

- [ ] **Step 2: Run the test to verify current boundary**

Run:

```powershell
python -m unittest tests.test_game_reverse_actions.TestGameReverseActions.test_rejects_raw_pointer_commands_as_public_actions
```

Expected: PASS, proving the existing public boundary already rejects raw pointer commands.

- [ ] **Step 3: Commit boundary test if it is the only change**

Do not commit yet if other task changes are already staged. This task is a guardrail and may be included with Task 2.

## Task 2: Internal Pointer Command Validator

**Files:**
- Create: `game_reverse/pointer_commands.py`
- Test: `tests/test_game_reverse_pointer_commands.py`

- [ ] **Step 1: Write failing validator tests**

Create `tests/test_game_reverse_pointer_commands.py`:

```python
# -*- coding: utf-8 -*-
"""Tests for internal continuous-control pointer command validation."""

import unittest

from game_reverse.pointer_commands import validate_pointer_command


class TestPointerCommands(unittest.TestCase):
    def test_accepts_touch_down_command(self):
        command = validate_pointer_command({"type": "touch_down", "x": 10, "y": 20}, (1080, 1920))

        self.assertEqual(command, {"type": "touch_down", "x": 10, "y": 20})

    def test_accepts_touch_move_with_duration(self):
        command = validate_pointer_command(
            {"type": "touch_move", "x": 100, "y": 200, "duration": 0.25},
            (1080, 1920),
        )

        self.assertEqual(command, {"type": "touch_move", "x": 100, "y": 200, "duration": 0.25})

    def test_accepts_touch_hold_with_seconds(self):
        command = validate_pointer_command({"type": "touch_hold", "seconds": 0.4}, (1080, 1920))

        self.assertEqual(command, {"type": "touch_hold", "seconds": 0.4})

    def test_accepts_touch_up_with_position(self):
        command = validate_pointer_command({"type": "touch_up", "x": 100, "y": 200}, (1080, 1920))

        self.assertEqual(command, {"type": "touch_up", "x": 100, "y": 200})

    def test_accepts_touch_up_without_position(self):
        command = validate_pointer_command({"type": "touch_up"}, (1080, 1920))

        self.assertEqual(command, {"type": "touch_up"})

    def test_rejects_out_of_bounds_pointer_position(self):
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            validate_pointer_command({"type": "touch_down", "x": 2000, "y": 20}, (1080, 1920))

    def test_rejects_invalid_duration(self):
        with self.assertRaisesRegex(ValueError, "duration"):
            validate_pointer_command({"type": "touch_move", "x": 100, "y": 200, "duration": 0}, (1080, 1920))

    def test_rejects_invalid_hold_seconds(self):
        with self.assertRaisesRegex(ValueError, "hold seconds"):
            validate_pointer_command({"type": "touch_hold", "seconds": 6}, (1080, 1920))

    def test_rejects_unknown_pointer_command(self):
        with self.assertRaisesRegex(ValueError, "pointer command"):
            validate_pointer_command({"type": "tap", "x": 10, "y": 20}, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m unittest tests.test_game_reverse_pointer_commands
```

Expected: FAIL with `ModuleNotFoundError: No module named 'game_reverse.pointer_commands'`.

- [ ] **Step 3: Implement validator**

Create `game_reverse/pointer_commands.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m unittest tests.test_game_reverse_pointer_commands tests.test_game_reverse_actions.TestGameReverseActions.test_rejects_raw_pointer_commands_as_public_actions
```

Expected: PASS.

## Task 3: Executor Pointer Primitive Execution and Cleanup

**Files:**
- Modify: `game_reverse/airtest_executor.py`
- Modify: `tests/test_game_reverse_airtest_executor.py`

- [ ] **Step 1: Write failing executor tests**

Append these test methods inside `TestAirtestExecutor`:

```python
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
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m unittest tests.test_game_reverse_airtest_executor.TestAirtestExecutor.test_executes_internal_pointer_commands_and_tracks_active_pointer tests.test_game_reverse_airtest_executor.TestAirtestExecutor.test_release_active_pointer_releases_last_position_once tests.test_game_reverse_airtest_executor.TestAirtestExecutor.test_pointer_command_requires_touch_api
```

Expected: FAIL with `AttributeError: 'AirtestExecutor' object has no attribute 'execute_pointer_command'`.

- [ ] **Step 3: Implement executor primitive support**

Modify `game_reverse/airtest_executor.py` so the class includes:

```python
class AirtestExecutor:
    def __init__(self, api=None):
        self.api = api or _load_airtest_api()
        self.pointer_active = False
        self.pointer_position = None

    ...

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

    def _require_touch_api(self, name):
        if not hasattr(self.api, name):
            raise RuntimeError("%s is required for internal pointer commands" % name)
```

Keep existing `execute`, `_hold_drag_release`, and `_load_airtest_api` behavior.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m unittest tests.test_game_reverse_airtest_executor
```

Expected: PASS.

## Task 4: Reuse Pointer Primitive Execution in Hold-Drag

**Files:**
- Modify: `game_reverse/airtest_executor.py`
- Modify: `tests/test_game_reverse_airtest_executor.py`

- [ ] **Step 1: Write failing cleanup test for hold-drag errors**

Add this fake API class after `FakeGestureApi`:

```python
class FailingMoveGestureApi(FakeGestureApi):
    def touch_move(self, pos, duration=0.5):
        self.calls.append(("touch_move", pos, duration))
        raise RuntimeError("move failed")
```

Append this test method inside `TestAirtestExecutor`:

```python
    def test_hold_drag_release_clears_pointer_state_when_move_fails(self):
        api = FailingMoveGestureApi()
        executor = AirtestExecutor(api=api)

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
        self.assertFalse(executor.pointer_active)
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
python -m unittest tests.test_game_reverse_airtest_executor.TestAirtestExecutor.test_hold_drag_release_clears_pointer_state_when_move_fails
```

Expected: FAIL because existing `_hold_drag_release` does not update `pointer_active` state.

- [ ] **Step 3: Refactor `_hold_drag_release` to use pointer commands**

Replace the gesture API branch in `_hold_drag_release` with:

```python
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
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m unittest tests.test_game_reverse_airtest_executor
```

Expected: PASS.

## Task 5: Full Phase 1 Verification and Commit

**Files:**
- Verify all files touched in Tasks 1-4.

- [ ] **Step 1: Run targeted phase tests**

Run:

```powershell
python -m unittest tests.test_game_reverse_actions tests.test_game_reverse_pointer_commands tests.test_game_reverse_airtest_executor
```

Expected: PASS.

- [ ] **Step 2: Run broader regression tests**

Run:

```powershell
python -m unittest tests.test_game_reverse_memory tests.test_game_reverse_profile_view tests.test_game_reverse_profile_learning tests.test_game_reverse_skill_library tests.test_game_reverse_state_graph tests.test_game_reverse_run_loop tests.test_game_reverse_llm_decider tests.test_game_reverse_feedback tests.test_game_reverse_goal_planner tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor tests.test_game_reverse_pointer_commands
```

Expected: PASS.

- [ ] **Step 3: Run syntax and diff checks**

Run:

```powershell
python -m py_compile game_reverse\actions.py game_reverse\airtest_executor.py game_reverse\pointer_commands.py tests\test_game_reverse_actions.py tests\test_game_reverse_airtest_executor.py tests\test_game_reverse_pointer_commands.py
git diff --check
```

Expected: no Python compile errors and no whitespace errors. Git may print LF/CRLF warnings on Windows.

- [ ] **Step 4: Commit Phase 1**

Run:

```powershell
git add -- game_reverse\airtest_executor.py game_reverse\pointer_commands.py tests\test_game_reverse_actions.py tests\test_game_reverse_airtest_executor.py tests\test_game_reverse_pointer_commands.py docs\superpowers\plans\2026-06-22-continuous-control-phase-1-pointer-primitives.md
git commit -m "feat: add internal pointer primitives"
```

Expected: commit succeeds and `git status --short` is clean.

## Self-Review

Spec coverage:

- Internal pointer commands are added without exposing raw `touch_*` commands publicly.
- Executor gets primitive command support and a cleanup hook.
- Existing one-shot actions remain compatible.
- `aim_fire`, visual anchors, Web continuous-action flags, controller loops, artifacts, and skill mining are intentionally deferred to later phases.

Placeholder scan:

- No task uses TBD/TODO/fill-in placeholders.
- Each code change includes concrete snippets.

Type consistency:

- The plan uses `validate_pointer_command`, `execute_pointer_command`, `release_active_pointer`, `pointer_active`, and `pointer_position` consistently.
