# Continuous Control Remaining Phases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete continuous-control phases 2 through 7 so the explorer can describe visual anchors, safely accept `aim_fire`, execute a bounded aiming loop, record control sessions, and mine reusable continuous-control skills.

**Architecture:** Keep raw `touch_*` commands internal. Add public `aim_fire` as the first composite continuous action, guarded by backend/Web opt-in and implemented through an `AimController` that writes grouped control-session artifacts. Store continuous-control success as parameterized skills while preserving existing discrete exploration behavior.

**Tech Stack:** Python `unittest`, existing `game_reverse` modules, static Web console JavaScript/CSS/HTML checks.

---

## Task 1: Visual Anchor Decision Schema

**Files:**
- Modify: `game_reverse/llm_decider.py`
- Modify: `tests/test_game_reverse_llm_decider.py`

- [ ] Add tests proving `parse_decision` preserves `detected_controls`, `detected_cursors`, `detected_targets`, and `control_hypothesis`, and older decisions default those fields to empty collections.
- [ ] Add tests proving `_build_decision_prompt` asks for visual anchors when direct actions have failed or gesture switching is recommended.
- [ ] Add normalizers for visual anchors and control hypotheses.
- [ ] Extend `_decision_schema()` with optional visual-anchor fields.
- [ ] Run `python -m unittest tests.test_game_reverse_llm_decider`.
- [ ] Commit with `feat: add visual anchor decision schema`.

## Task 2: `aim_fire` Action and Safety Gates

**Files:**
- Modify: `game_reverse/actions.py`
- Modify: `game_reverse/config.py`
- Modify: `game_reverse/web_service.py`
- Modify: `web/app.js`
- Modify: `web/index.html`
- Modify: `web/styles.css`
- Modify: `tests/test_game_reverse_actions.py`
- Modify: `tests/test_game_reverse_config.py`
- Modify: `tests/test_game_reverse_web_service.py`
- Modify: `tests/test_web_console_static.py`

- [ ] Add failing tests for validating `aim_fire` anchors, rejecting malformed anchors, and still rejecting raw `touch_*` public actions.
- [ ] Add `enable_continuous_actions` to `GameReverseConfig` with default `False`.
- [ ] Add `aim_fire` to public safe-action names but require it to appear in `allowed_actions`.
- [ ] Add Web/API validation: `aim_fire` requires `enable_unsafe_actions=true` and `enable_continuous_actions=true`.
- [ ] Add Web UI opt-in for continuous gestures; include `aim_fire` only when both unsafe and continuous toggles are on.
- [ ] Run `python -m unittest tests.test_game_reverse_actions tests.test_game_reverse_config tests.test_game_reverse_web_service tests.test_web_console_static`.
- [ ] Commit with `feat: gate aim fire continuous action`.

## Task 3: Control Session Journal and AimController

**Files:**
- Create: `game_reverse/continuous_control.py`
- Modify: `game_reverse/journal.py`
- Modify: `tests/test_game_reverse_continuous_control.py`
- Modify: `tests/test_game_reverse_journal.py`

- [ ] Add failing tests for control screenshot naming and `control_sessions.jsonl` writes.
- [ ] Add failing tests for `AimController.execute()` calling `touch_down`, `touch_hold`, bounded `touch_move`, `touch_up`, and cleanup on errors.
- [ ] Implement `Journal.control_screen_path()` and `Journal.write_control_event()`.
- [ ] Implement `AimController` with bounded geometry movement and internal pointer commands.
- [ ] Run `python -m unittest tests.test_game_reverse_continuous_control tests.test_game_reverse_journal`.
- [ ] Commit with `feat: add aim controller control sessions`.

## Task 4: Run Loop Integration

**Files:**
- Modify: `game_reverse/run_loop.py`
- Modify: `tests/test_game_reverse_run_loop.py`

- [ ] Add failing integration test where a decider emits `aim_fire`, a fake executor records internal pointer commands, and the run loop writes action, observation, feedback, and control-session artifacts.
- [ ] Route `aim_fire` through `AimController` instead of direct `executor.execute`.
- [ ] Include visual-anchor fields in observations.
- [ ] Attach `control_feedback` to action and feedback artifacts when available.
- [ ] Ensure executor cleanup runs before finalization if a continuous action errors.
- [ ] Run `python -m unittest tests.test_game_reverse_run_loop`.
- [ ] Commit with `feat: execute aim fire in run loop`.

## Task 5: Continuous Feedback and Skill Mining

**Files:**
- Modify: `game_reverse/feedback.py`
- Modify: `game_reverse/skill_library.py`
- Modify: `game_reverse/profile_learning.py`
- Modify: `tests/test_game_reverse_feedback.py`
- Modify: `tests/test_game_reverse_skill_library.py`
- Modify: `tests/test_game_reverse_profile_learning.py`

- [ ] Add tests mapping `counter_changed` to `target_collected` for continuous actions and repeated no-change to `control_attempt_failed`.
- [ ] Add tests mining successful `aim_fire` actions into `continuous_control` parameterized skills.
- [ ] Add memory summary coverage for continuous-control skills.
- [ ] Implement feedback mapping and skill mining.
- [ ] Run `python -m unittest tests.test_game_reverse_feedback tests.test_game_reverse_skill_library tests.test_game_reverse_profile_learning`.
- [ ] Commit with `feat: learn continuous control skills`.

## Task 6: Controller Registry and Generalization Boundary

**Files:**
- Modify: `game_reverse/continuous_control.py`
- Modify: `tests/test_game_reverse_continuous_control.py`

- [ ] Add tests proving only registered single-pointer controllers are available by default.
- [ ] Add a small `ContinuousControllerRegistry` with `AimController` registered and multi-touch disabled.
- [ ] Ensure future controller names are rejected with a clear error.
- [ ] Run `python -m unittest tests.test_game_reverse_continuous_control`.
- [ ] Commit with `feat: add continuous controller registry`.

## Task 7: Final Verification

**Files:**
- Verify all touched files.

- [ ] Run targeted tests:

```powershell
python -m unittest tests.test_game_reverse_actions tests.test_game_reverse_config tests.test_game_reverse_llm_decider tests.test_game_reverse_continuous_control tests.test_game_reverse_journal tests.test_game_reverse_run_loop tests.test_game_reverse_feedback tests.test_game_reverse_skill_library tests.test_game_reverse_profile_learning tests.test_game_reverse_web_service tests.test_web_console_static
```

- [ ] Run broader regression tests:

```powershell
python -m unittest tests.test_game_reverse_memory tests.test_game_reverse_profile_view tests.test_game_reverse_profile_learning tests.test_game_reverse_skill_library tests.test_game_reverse_state_graph tests.test_game_reverse_run_loop tests.test_game_reverse_llm_decider tests.test_game_reverse_feedback tests.test_game_reverse_goal_planner tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor tests.test_game_reverse_pointer_commands tests.test_game_reverse_continuous_control tests.test_game_reverse_journal tests.test_game_reverse_config
```

- [ ] Run syntax and diff checks:

```powershell
python -m py_compile game_reverse\actions.py game_reverse\config.py game_reverse\continuous_control.py game_reverse\feedback.py game_reverse\journal.py game_reverse\llm_decider.py game_reverse\run_loop.py game_reverse\skill_library.py game_reverse\web_service.py
git diff --check
```

- [ ] Restart the Web service with `.\restart-web.bat`.
- [ ] Commit any final fixes.

## Self-Review

Spec coverage:

- Phase 2 is Task 1.
- Phase 3 is Task 2.
- Phase 4 is Tasks 3 and 4.
- Phase 5 is Task 5.
- Phase 6 and Phase 7 boundaries are Task 6.

Intentional limits:

- Multi-touch remains disabled.
- Raw `touch_*` commands remain internal.
- `aim_fire` is the only executable continuous composite in this pass.
