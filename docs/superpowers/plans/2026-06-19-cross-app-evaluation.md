# Cross-App Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline evaluation surface that measures explorer generality across ordinary apps, menu-heavy games, and pure-render games.

**Architecture:** Add a read-only evaluator that consumes existing session artifacts and produces normalized metrics per run. A comparison layer groups runs by benchmark scenario, exposes regression flags, and writes Markdown/JSON reports without requiring a device or LLM.

**Tech Stack:** Python standard library, JSON/JSONL artifacts, Markdown reports, existing `unittest`/`pytest` tests.

---

## File Structure

- Create `game_reverse/evaluation.py`: benchmark scenario definitions, session metric collection, comparison summaries, regression detection, Markdown report writer, and small CLI.
- Create `tests/test_game_reverse_evaluation.py`: tests for benchmark scenarios, metrics, comparison reports, and CLI JSON output.

---

### Task 1: Session Metrics and Benchmark Scenarios

**Files:**
- Create: `game_reverse/evaluation.py`
- Create: `tests/test_game_reverse_evaluation.py`

- [x] **Step 1: Write failing metric tests**

Create temporary session directories with `state_map.json`, `actions.jsonl`, `skill_attempts.jsonl`, `goals.json`, and `observations.jsonl`. Assert:

- `default_benchmark_scenarios()` includes `ordinary_app`, `menu_heavy_game`, and `pure_render_game`
- `collect_session_metrics(session_dir, scenario_id="menu_heavy_game")` returns state count, transition count, useful transitions, visible effect rate, no-change count, unsafe avoidance count, skill success/failure counts, skill reuse rate, subgoals completed, progress depth, and LLM calls per useful transition

- [x] **Step 2: Verify tests fail for missing module**

Run:

```bash
python -m pytest tests/test_game_reverse_evaluation.py -q
```

Expected: FAIL with missing `game_reverse.evaluation`.

- [x] **Step 3: Implement metrics reader**

Implement:

```python
def default_benchmark_scenarios():
    ...

def collect_session_metrics(session_dir, scenario_id="unclassified"):
    ...
```

Use safe defaults for missing files. Count useful transitions from state map classifications excluding `no_change`. Count visible effects from successful feedback results. Count unsafe avoidance from `sensitive_screen` or `safety_label == "sensitive"`. Count profile reuse from `action_source == "skill"`.

- [x] **Step 4: Verify metric tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_evaluation.py -q
```

Expected: PASS.

---

### Task 2: Comparison Report and CLI

**Files:**
- Modify: `game_reverse/evaluation.py`
- Modify: `tests/test_game_reverse_evaluation.py`

- [x] **Step 1: Write failing comparison and CLI tests**

Add tests that:

- compare two sessions in the same scenario and surface regression flags when the later run discovers fewer states or useful transitions
- write a Markdown report containing scenario names, states discovered, useful transitions, unsafe screens avoided, skill reuse rate, progress depth, and regression notes
- invoke `evaluation.main([...])` with `--json-output` and `--markdown-output`

- [x] **Step 2: Verify tests fail for missing comparison/report functions**

Run:

```bash
python -m pytest tests/test_game_reverse_evaluation.py -q
```

Expected: FAIL because comparison/report helpers are missing.

- [x] **Step 3: Implement comparison/report helpers**

Implement:

```python
def compare_sessions(session_dirs, scenario_id="unclassified"):
    ...

def write_comparison_report(comparison, markdown_path):
    ...

def write_comparison_json(comparison, json_path):
    ...

def main(argv=None):
    ...
```

Sort runs by `session_id`, compare adjacent runs inside each scenario, and emit regression flags for decreases in `states_discovered`, `useful_transitions`, `visible_effect_rate`, `skill_reuse_rate`, or `progress_depth`.

- [x] **Step 4: Verify comparison tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_evaluation.py -q
```

Expected: PASS.

---

### Task 3: Phase 8 Acceptance Verification and Commit

- [x] **Step 1: Run focused regression**

Run:

```bash
python -m pytest tests/test_game_reverse_evaluation.py -q
```

Expected: PASS.

- [x] **Step 2: Run full game_reverse regression suite**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_affordances.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_config.py tests/test_game_reverse_evaluation.py tests/test_game_reverse_executors.py tests/test_game_reverse_feedback.py tests/test_game_reverse_goal_planner.py tests/test_game_reverse_journal.py tests/test_game_reverse_lightweight_runner.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_memory.py tests/test_game_reverse_mission.py tests/test_game_reverse_profile_view.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_skill_library.py tests/test_game_reverse_state_graph.py tests/test_game_reverse_target_discovery.py tests/test_game_reverse_web_server.py tests/test_game_reverse_web_service.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [x] **Step 3: Commit Phase 8**

Run:

```bash
git add docs/superpowers/plans/2026-06-19-cross-app-evaluation.md game_reverse/evaluation.py tests/test_game_reverse_evaluation.py
git commit -m "feat: add cross-app evaluation reports"
```
