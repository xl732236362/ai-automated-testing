# Game Runner Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Web Runner latency/token cost and improve gameplay discovery by adding richer gestures, structured exploration, lightweight stepping, compact context, and automated hit feedback.

**Architecture:** Keep the existing Web Runner and executor registry, but move gameplay exploration toward a constrained action protocol. The first two phases extend the action schema and prompt contract; later phases can add a lightweight per-step runner without replacing the Codex CLI adapter.

**Tech Stack:** Python `unittest`, Airtest API wrapper, local Web Runner service, Codex CLI executor prompt contract.

---

### Phase 1: Gesture Action Capability

**Files:**
- Modify: `game_reverse/actions.py`
- Modify: `game_reverse/airtest_executor.py`
- Modify: `tests/test_game_reverse_actions.py`
- Modify: `tests/test_game_reverse_airtest_executor.py`

- [ ] Add a `hold_drag_release` action type that validates `x1`, `y1`, `x2`, `y2`, `hold_seconds`, and `duration`.
- [ ] Execute `hold_drag_release` through the Airtest API as a swipe from press point to release point with the requested duration.
- [ ] Keep validation conservative: coordinates must be in screen bounds, `hold_seconds` between `0` and `5`, `duration` between `0` and `5`.
- [ ] Verify with `python -m unittest tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor`.

### Phase 2: Mandatory Gesture Exploration Matrix

**Files:**
- Modify: `game_reverse/config.py`
- Modify: `game_reverse/web_service.py`
- Modify: `game_reverse/executors.py`
- Modify: `tests/test_game_reverse_config.py`
- Modify: `tests/test_game_reverse_web_service.py`
- Modify: `tests/test_game_reverse_executors.py`

- [ ] Include `hold_drag_release` in default allowed actions.
- [ ] Add prompt instructions that gameplay exploration must test direct tap, scene drag, fire tap, long press, and hold-drag-release when unsafe actions are enabled.
- [ ] Make the Codex prompt explain when to use `hold_drag_release`: press the gameplay control, drag toward the target or aiming direction, then release.
- [ ] Verify with `python -m unittest tests.test_game_reverse_config tests.test_game_reverse_web_service tests.test_game_reverse_executors`.

### Phase 3: Lightweight Step Runner

**Files:**
- Create: `game_reverse/lightweight_runner.py`
- Modify: `game_reverse/web_service.py`
- Modify: `game_reverse/executors.py`
- Add tests under `tests/test_game_reverse_lightweight_runner.py`

- [ ] Add a runner that owns screenshot capture, action execution, and artifact writing.
- [ ] Restrict the model/agent responsibility to returning one JSON action per step.
- [ ] Avoid broad repo inspection inside each gameplay turn.
- [ ] Verify that a 10-step fake run writes screenshots, actions, observations, and a final report.

### Phase 4: Compact Context Budget

**Files:**
- Modify: `game_reverse/llm_decider.py`
- Modify: `game_reverse/run_loop.py`
- Add focused tests under `tests/test_game_reverse_llm_decider.py`

- [ ] Pass only current screenshot, mission, recent `N` action summaries, and compact target state.
- [ ] Stop sending full historical reports or large logs into each decision.
- [ ] Add explicit context size guards for serialized prompts.
- [ ] Verify that recent history is bounded and old action details are omitted.

### Phase 5: Hit Feedback Strategy

**Files:**
- Create: `game_reverse/feedback.py`
- Modify: `game_reverse/run_loop.py`
- Add tests under `tests/test_game_reverse_feedback.py`

- [ ] Compare before/after screenshots or structured observations to classify `counter_changed`, `tray_changed`, or `no_visible_change`.
- [ ] Feed the classified result into the next decision.
- [ ] Add strategy rules: when `no_visible_change`, perform fine aim correction or switch gesture hypothesis instead of repeating the same action.
- [ ] Verify with synthetic observations that repeated misses trigger a different action family.

### Execution Notes

- Implement phases independently and commit after each verified phase.
- Phase 1 and Phase 2 are the current execution target.
- Phase 3-5 should wait until a real run confirms the expanded gesture matrix improves discovery.
