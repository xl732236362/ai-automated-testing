# Affordance Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 2 affordance discovery so each run records likely interactive regions, de-duplicates them per state, and tracks feedback from tested regions.

**Architecture:** Add a focused `game_reverse.affordances` module that normalizes region bounds from OCR, UI nodes, visual regions, and LLM-proposed regions. Integrate it after action feedback in `run_loop` so run-local `affordances.json` is written without changing action selection yet.

**Tech Stack:** Python standard library, JSON artifacts, existing `unittest`/`pytest` tests, existing `game_reverse` runner and journal.

---

## File Structure

- Create `game_reverse/affordances.py`: owns region normalization, per-state de-duplication, confidence updates, and serializable affordance maps.
- Create `tests/test_game_reverse_affordances.py`: unit tests for OCR/UI/visual/LLM region extraction, de-duplication, and feedback updates.
- Modify `game_reverse/journal.py`: add `write_affordances()`.
- Modify `tests/test_game_reverse_journal.py`: verify `affordances.json` is written as readable JSON.
- Modify `game_reverse/run_loop.py`: update affordance memory per observation and tested action, then write `affordances.json`.
- Modify `tests/test_game_reverse_run_loop.py`: verify run artifacts include affordances and repeated no-change action feedback marks a region as deprioritized.

---

### Task 1: Affordance Core

**Files:**
- Create: `game_reverse/affordances.py`
- Test: `tests/test_game_reverse_affordances.py`

- [ ] **Step 1: Write failing tests**

Create tests that:

- collect OCR regions with `bounds`
- collect UI nodes with `bounds`
- collect visual regions with `bounds`
- collect LLM-proposed regions with `bounds`
- de-duplicate identical or near-identical regions in the same state
- update `last_result`, `tested_count`, and `status` after no-change feedback

- [ ] **Step 2: Verify tests fail for missing module**

Run:

```bash
python -m pytest tests/test_game_reverse_affordances.py -q
```

Expected: FAIL with missing `game_reverse.affordances`.

- [ ] **Step 3: Implement minimal core**

Implement:

```python
class AffordanceMemory:
    def collect_from_observation(self, state_id, observation, screen_size=None): ...
    def record_action_feedback(self, state_id, action, feedback_result): ...
    def to_affordances(self): ...
```

Use stable ids derived from state id, source, normalized bounds, action type, and label. Supported action types begin with `tap`; visual regions can also support `swipe` if supplied by source.

- [ ] **Step 4: Verify affordance tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_affordances.py -q
```

Expected: PASS.

---

### Task 2: Journal Writer

**Files:**
- Modify: `game_reverse/journal.py`
- Modify: `tests/test_game_reverse_journal.py`

- [ ] **Step 1: Write failing journal test**

Add a test calling:

```python
journal.write_affordances({"version": 1, "states": {"state_abc": []}})
```

Assert `affordances.json` parses as JSON.

- [ ] **Step 2: Verify failure**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py -q
```

Expected: FAIL because `write_affordances` does not exist.

- [ ] **Step 3: Implement writer**

Add `write_affordances()` using sorted, indented JSON.

- [ ] **Step 4: Verify journal tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py -q
```

Expected: PASS.

---

### Task 3: Run Loop Integration

**Files:**
- Modify: `game_reverse/run_loop.py`
- Modify: `tests/test_game_reverse_run_loop.py`

- [ ] **Step 1: Write failing run-loop test**

Use a fake decider that returns observation metadata:

```python
"ocr": [{"text": "Start", "bounds": [100, 200, 220, 260]}],
"ui_nodes": [{"text": "Start", "class": "Button", "bounds": [100, 200, 220, 260]}],
"visual_regions": [{"bounds": [500, 900, 700, 1050], "reason": "large button"}],
"proposed_regions": [{"bounds": [100, 200, 220, 260], "label": "start button"}],
```

Assert `affordances.json` exists, contains de-duplicated candidates for the state, and records a no-change feedback result after a tap in a candidate region.

- [ ] **Step 2: Verify failure**

Run:

```bash
python -m pytest tests/test_game_reverse_run_loop.py -q
```

Expected: FAIL because run-loop does not write affordance artifacts.

- [ ] **Step 3: Integrate affordance memory**

After `state_graph.update()`, pass observation metadata into `AffordanceMemory.collect_from_observation()`. After feedback classification, call `record_action_feedback()` for tap/swipe/hold-drag actions. Write `affordances.json` after each successful step and at run end.

- [ ] **Step 4: Verify run-loop tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

---

### Task 4: Phase 2 Acceptance Verification

- [ ] **Step 1: Run focused Phase 2 tests**

Run:

```bash
python -m pytest tests/test_game_reverse_affordances.py tests/test_game_reverse_journal.py tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full game_reverse regression suite**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_affordances.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_config.py tests/test_game_reverse_executors.py tests/test_game_reverse_feedback.py tests/test_game_reverse_journal.py tests/test_game_reverse_lightweight_runner.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_mission.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_state_graph.py tests/test_game_reverse_target_discovery.py tests/test_game_reverse_web_server.py tests/test_game_reverse_web_service.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit Phase 2**

Run:

```bash
git add docs/superpowers/plans/2026-06-19-affordance-discovery.md game_reverse/affordances.py game_reverse/journal.py game_reverse/run_loop.py tests/test_game_reverse_affordances.py tests/test_game_reverse_journal.py tests/test_game_reverse_run_loop.py
git commit -m "feat: add affordance discovery artifacts"
```
