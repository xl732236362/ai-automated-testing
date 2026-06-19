# Goal Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 6 goal planning so runs maintain main/subgoal lifecycle, emit goal events, avoid completed subgoals, and report progress or blocked reasons.

**Architecture:** Add `game_reverse.goal_planner` as a deterministic goal lifecycle module. It derives a simple generic goal ladder from the mission, updates subgoals from feedback/state labels, and writes JSON artifacts. The first version does not call an LLM replanner directly; it creates the hook and persisted context that later LLM replanning can consume.

**Tech Stack:** Python standard library, JSON/JSONL artifacts, existing `unittest`/`pytest` tests, existing runner/report writer.

---

## File Structure

- Create `game_reverse/goal_planner.py`: goal stack schema, lifecycle updates, blocked/completed transitions, and serializable payloads.
- Create `tests/test_game_reverse_goal_planner.py`: unit tests for lifecycle transitions, avoiding completed subgoals, and blocked recovery candidates.
- Modify `game_reverse/journal.py`: add `goal_events.jsonl` and `goals.json` writers.
- Modify `tests/test_game_reverse_journal.py`: verify goal artifacts.
- Modify `game_reverse/memory.py`: initialize profile `goals.json`.
- Modify `tests/test_game_reverse_memory.py`: verify profile `goals.json`.
- Modify `game_reverse/run_loop.py`: update goal planner every step and persist session/profile goal artifacts.
- Modify `game_reverse/report_writer.py`: include goal progress and blocked reasons in final report.
- Modify `tests/test_game_reverse_run_loop.py` and `tests/test_game_reverse_report_writer.py`: verify run/report integration.

---

### Task 1: Goal Planner Core

**Files:**
- Create: `game_reverse/goal_planner.py`
- Test: `tests/test_game_reverse_goal_planner.py`

- [x] **Step 1: Write failing tests**

Add tests for:

- initial goal stack from mission
- completing active subgoal on `level_started` / `level_completed`
- blocking active subgoal on `sensitive_screen` / repeated failure
- selecting next candidate while avoiding completed subgoals

- [x] **Step 2: Verify tests fail for missing module**

Run:

```bash
python -m pytest tests/test_game_reverse_goal_planner.py -q
```

Expected: FAIL with missing `game_reverse.goal_planner`.

- [x] **Step 3: Implement planner**

Implement:

```python
class GoalPlanner:
    def __init__(self, mission, existing=None): ...
    def update(self, observation, action_record, feedback): ...
    def to_goals(self): ...
```

- [x] **Step 4: Verify goal planner tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_goal_planner.py -q
```

Expected: PASS.

---

### Task 2: Artifacts and Profile Support

**Files:**
- Modify: `game_reverse/journal.py`
- Modify: `tests/test_game_reverse_journal.py`
- Modify: `game_reverse/memory.py`
- Modify: `tests/test_game_reverse_memory.py`

- [x] **Step 1: Write failing artifact tests**

Assert `Journal.write_goal_event()` writes JSONL, `Journal.write_goals()` writes JSON, and `ProfileStore.initialize()` creates `goals.json`.

- [x] **Step 2: Implement artifact support**

Add writers and default:

```json
{"version": 1, "main_goal": "", "active_subgoal": "", "completed_subgoals": [], "blocked_subgoals": [], "next_candidates": []}
```

- [x] **Step 3: Verify tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py -q
```

Expected: PASS.

---

### Task 3: Run Loop and Report Integration

**Files:**
- Modify: `game_reverse/run_loop.py`
- Modify: `game_reverse/report_writer.py`
- Modify: `tests/test_game_reverse_run_loop.py`
- Modify: `tests/test_game_reverse_report_writer.py`

- [x] **Step 1: Write failing integration tests**

Assert a run writes `goals.json` and `goal_events.jsonl`, action records include `active_subgoal`, and final report includes goal progress and blocked reason text.

- [x] **Step 2: Implement integration**

Create `GoalPlanner` at run start, update it after feedback, persist session/profile goal artifacts, and include goal fields in action/observation records.

- [x] **Step 3: Verify focused tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_goal_planner.py tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_report_writer.py -q
```

Expected: PASS.

---

### Task 4: Phase 6 Acceptance Verification and Commit

- [x] **Step 1: Run full game_reverse regression suite**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_affordances.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_config.py tests/test_game_reverse_executors.py tests/test_game_reverse_feedback.py tests/test_game_reverse_goal_planner.py tests/test_game_reverse_journal.py tests/test_game_reverse_lightweight_runner.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_memory.py tests/test_game_reverse_mission.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_skill_library.py tests/test_game_reverse_state_graph.py tests/test_game_reverse_target_discovery.py tests/test_game_reverse_web_server.py tests/test_game_reverse_web_service.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [x] **Step 2: Commit Phase 6**

Run:

```bash
git add docs/superpowers/plans/2026-06-19-goal-planner.md game_reverse/goal_planner.py game_reverse/journal.py game_reverse/memory.py game_reverse/report_writer.py game_reverse/run_loop.py tests/test_game_reverse_goal_planner.py tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py
git commit -m "feat: add goal planner lifecycle"
```
