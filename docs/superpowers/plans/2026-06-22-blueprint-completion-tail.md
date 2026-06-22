# Blueprint Completion Tail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining Universal App/Game Explorer blueprint details that were left as future-facing architecture after Phase 1-8.

**Architecture:** Keep the existing `game_reverse` package layout and add small compatibility layers rather than moving stable modules. The run loop remains the integration point, while journal/profile artifacts, targeted action resolution, and LLM role wrappers become independently testable modules.

**Tech Stack:** Python standard library, existing `pytest` tests, JSON/JSONL artifacts, current Airtest executor boundary.

---

## File Structure

- Modify `game_reverse/journal.py`: add `feedback.jsonl` writer and `run_summary.json` writer.
- Modify `game_reverse/run_loop.py`: write feedback records, run summaries, and profile trace JSONL files.
- Modify `game_reverse/memory.py`: initialize and append `traces/<run_id>.jsonl`.
- Modify `game_reverse/actions.py`: accept and resolve `tap_target`, `swipe_target`, and `hold_drag_target`.
- Modify `game_reverse/skill_library.py`: replay targeted actions through the action validator.
- Create `game_reverse/llm_roles.py`: thin wrappers for state analysis, action proposal, rule mining, skill mining, and goal replanning.
- Modify `game_reverse/goal_planner.py`: expose a replan hook that can accept LLM role output.
- Add/modify tests under `tests/test_game_reverse_*.py` for each behavior.

---

### Task 1: Artifact Contract and Profile Traces

**Files:**
- Modify: `game_reverse/journal.py`
- Modify: `game_reverse/memory.py`
- Modify: `game_reverse/run_loop.py`
- Test: `tests/test_game_reverse_journal.py`
- Test: `tests/test_game_reverse_memory.py`
- Test: `tests/test_game_reverse_run_loop.py`

- [ ] **Step 1: Write failing tests**

Assert a run writes `feedback.jsonl`, `run_summary.json`, and profile `traces/<session_name>.jsonl`.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py tests/test_game_reverse_run_loop.py -q
```

Expected: FAIL because the new artifact writers and trace helpers do not exist.

- [ ] **Step 3: Implement artifact writers**

Add `Journal.write_feedback(record)`, `Journal.write_run_summary(summary)`, and `ProfileStore.append_trace(run_id, event)`.

- [ ] **Step 4: Integrate run loop**

Write one feedback record per successful step, append one profile trace event per successful step, and write a final summary with session id, stop reason, counts, and final goals.

- [ ] **Step 5: Verify and commit**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

Commit:

```bash
git add docs/superpowers/plans/2026-06-22-blueprint-completion-tail.md game_reverse/journal.py game_reverse/memory.py game_reverse/run_loop.py tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py tests/test_game_reverse_run_loop.py
git commit -m "feat: complete explorer artifact contract"
```

### Task 2: Targeted Actions

**Files:**
- Modify: `game_reverse/actions.py`
- Modify: `game_reverse/skill_library.py`
- Test: `tests/test_game_reverse_actions.py`
- Test: `tests/test_game_reverse_skill_library.py`

- [ ] **Step 1: Write failing tests**

Assert `tap_target`, `swipe_target`, and `hold_drag_target` resolve bounded target rectangles into primitive actions. Assert skill replay can execute targeted steps.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_skill_library.py -q
```

Expected: FAIL because targeted action types are not supported.

- [ ] **Step 3: Implement targeted action resolution**

Extend `validate_action()` to accept the targeted action types when allowed, resolve bounds to center points, and return primitive `tap`, `swipe`, or `hold_drag_release` actions with `target_ref` metadata preserved when present.

- [ ] **Step 4: Verify and commit**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_skill_library.py -q
```

Expected: PASS.

Commit:

```bash
git add game_reverse/actions.py game_reverse/skill_library.py tests/test_game_reverse_actions.py tests/test_game_reverse_skill_library.py
git commit -m "feat: add targeted action resolution"
```

### Task 3: LLM Role Boundaries and Replanning Hook

**Files:**
- Create: `game_reverse/llm_roles.py`
- Modify: `game_reverse/goal_planner.py`
- Modify: `game_reverse/run_loop.py`
- Test: `tests/test_game_reverse_llm_roles.py`
- Test: `tests/test_game_reverse_goal_planner.py`
- Test: `tests/test_game_reverse_run_loop.py`

- [ ] **Step 1: Write failing tests**

Assert role wrappers can call a decider-like backend for state analysis and action proposal, deterministic rule/skill mining delegates to existing modules, and `GoalPlanner.replan()` can accept a role output to update active/next goals.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m pytest tests/test_game_reverse_llm_roles.py tests/test_game_reverse_goal_planner.py tests/test_game_reverse_run_loop.py -q
```

Expected: FAIL because `game_reverse.llm_roles` and `GoalPlanner.replan()` do not exist.

- [ ] **Step 3: Implement role wrappers and planner hook**

Add simple role classes/functions around the current decider, `SkillLibrary.mine_candidates()`, and `GoalPlanner.replan()`. Integrate the hook after repeated no-change recovery so future LLM replanners have a stable call site without forcing LLM calls every step.

- [ ] **Step 4: Verify and commit**

Run:

```bash
python -m pytest tests/test_game_reverse_llm_roles.py tests/test_game_reverse_goal_planner.py tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

Commit:

```bash
git add game_reverse/llm_roles.py game_reverse/goal_planner.py game_reverse/run_loop.py tests/test_game_reverse_llm_roles.py tests/test_game_reverse_goal_planner.py tests/test_game_reverse_run_loop.py
git commit -m "feat: add explorer llm role hooks"
```

### Task 4: Final Regression

- [ ] **Step 1: Run full game_reverse suite**

Run:

```bash
python -c "import pathlib, subprocess, sys; files=[str(p) for p in pathlib.Path('tests').glob('test_game_reverse_*.py')]; raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', *files, '-q']))"
```

Expected: PASS.

- [ ] **Step 2: Summarize remaining non-goals**

Confirm no remaining blueprint implementation gaps except non-goals such as guaranteed game completion or app injection.
