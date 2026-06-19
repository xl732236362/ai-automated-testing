# State Graph Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 1 state graph artifacts so each run records reusable state ids, state transitions, and a run-local `state_map.json`.

**Architecture:** Add a focused `game_reverse.state_graph` module that derives conservative state identities from observation text and screenshot content, tracks state nodes and transitions in memory, and exposes JSON-serializable records. Integrate it at the journal/run-loop boundary so Phase 1 adds artifacts without changing action selection behavior.

**Tech Stack:** Python standard library, JSON/JSONL artifacts, existing `unittest`/`pytest` tests, existing `game_reverse` runner and journal.

---

## File Structure

- Create `game_reverse/state_graph.py`: owns state id generation, run-local state map, transition classification, and serializable transition records.
- Create `tests/test_game_reverse_state_graph.py`: unit tests for stable state id reuse, new-state creation, no-change classification, and transition serialization.
- Modify `game_reverse/journal.py`: create and write `state_transitions.jsonl`, write `state_map.json`.
- Modify `tests/test_game_reverse_journal.py`: verify the new state graph artifacts are written as readable JSON/JSONL.
- Modify `game_reverse/run_loop.py`: update state graph after each observation, attach state metadata to observation/action records, and persist state artifacts.
- Modify `tests/test_game_reverse_run_loop.py`: verify a fake multi-step run writes state ids, transition records, and `state_map.json`.

---

### Task 1: State Graph Core

**Files:**
- Create: `game_reverse/state_graph.py`
- Test: `tests/test_game_reverse_state_graph.py`

- [ ] **Step 1: Write failing tests for state identity and transitions**

Create `tests/test_game_reverse_state_graph.py` with tests that import `StateGraph`, build observations with stable summaries/states/screens, and assert:

```python
graph = StateGraph()
first = graph.update(step=1, screen_path="screens/step_0001.png", observation={"state": "home", "screen_summary": "Main menu"})
second = graph.update(step=2, screen_path="screens/step_0002.png", observation={"state": "home", "screen_summary": "Main menu"})

self.assertEqual(first["state_id"], second["state_id"])
self.assertEqual(second["transition"]["classification"], "no_change")
```

Add a second test with different observation text and assert `entered_new_state`. Add a third test that `to_state_map()` contains `states`, `transitions`, and `version`.

- [ ] **Step 2: Verify the tests fail for missing module**

Run:

```bash
python -m pytest tests/test_game_reverse_state_graph.py -q
```

Expected: FAIL with `ModuleNotFoundError` or import error for `game_reverse.state_graph`.

- [ ] **Step 3: Implement the minimal state graph**

Implement `StateGraph` with:

```python
class StateGraph:
    def update(self, step, screen_path, observation, screenshot_hash=None): ...
    def to_state_map(self): ...
```

Use deterministic ids such as `state_<sha1-prefix>`, using screenshot hash when available and otherwise normalized `state`, `screen_summary`, and screenshot tags. Track first/last seen step, visit count, representative screen, signatures, and transitions.

- [ ] **Step 4: Verify state graph tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_state_graph.py -q
```

Expected: PASS.

---

### Task 2: Journal Artifact Writers

**Files:**
- Modify: `game_reverse/journal.py`
- Modify: `tests/test_game_reverse_journal.py`

- [ ] **Step 1: Write failing journal tests**

Add a journal test that calls:

```python
journal.write_state_transition({"step": 1, "from_state_id": None, "to_state_id": "state_abc"})
journal.write_state_map({"version": 1, "states": {"state_abc": {}}, "transitions": []})
```

Then assert `state_transitions.jsonl` parses as JSONL and `state_map.json` parses as JSON.

- [ ] **Step 2: Verify the journal test fails**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py -q
```

Expected: FAIL because `Journal` does not yet expose the new methods or files.

- [ ] **Step 3: Implement artifact writers**

Update `Journal.create()` to initialize `state_transitions.jsonl`, add `write_state_transition()`, and add `write_state_map()` that writes sorted, human-readable JSON.

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

Add a test using the existing fake executor/decider shape with three steps: first and second observations are the same state, third observation is different. Assert:

```python
state_map_path = os.path.join(session_dir, "state_map.json")
transitions_path = os.path.join(session_dir, "state_transitions.jsonl")
self.assertTrue(os.path.exists(state_map_path))
self.assertTrue(os.path.exists(transitions_path))
```

Parse `observations.jsonl` and assert every observation has `state_id`. Parse transitions and assert at least one `no_change` transition and one `entered_new_state` transition.

- [ ] **Step 2: Verify the run-loop test fails**

Run:

```bash
python -m pytest tests/test_game_reverse_run_loop.py -q
```

Expected: FAIL because run-loop does not yet persist state graph artifacts.

- [ ] **Step 3: Integrate `StateGraph` in `run_loop`**

After building `observation_record`, call `state_graph.update(...)`. Copy returned `state_id`, `state_visit_count`, and transition classification into the observation record. Copy `state_id` and transition classification into the action record for easier audit. Write transition records each step and write `state_map.json` after updates and at run end.

- [ ] **Step 4: Verify run-loop tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

---

### Task 4: Phase 1 Acceptance Verification

**Files:**
- No additional production files expected.

- [ ] **Step 1: Run focused Phase 1 test suite**

Run:

```bash
python -m pytest tests/test_game_reverse_state_graph.py tests/test_game_reverse_journal.py tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full game_reverse regression suite**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_config.py tests/test_game_reverse_executors.py tests/test_game_reverse_feedback.py tests/test_game_reverse_journal.py tests/test_game_reverse_lightweight_runner.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_mission.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_state_graph.py tests/test_game_reverse_target_discovery.py tests/test_game_reverse_web_server.py tests/test_game_reverse_web_service.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [ ] **Step 3: Phase 1 coverage self-review**

Check the blueprint Phase 1 acceptance against code and tests:

- 20-step readability is represented by human-readable `state_map.json` and JSONL transition records.
- Repeated screens reuse state ids in `StateGraph` unit tests and run-loop integration tests.
- No-change actions are visible in transition records via `classification: "no_change"`.
- Tests cover state id generation and transition writing.

If any item lacks direct evidence, add a test or artifact field before moving to Phase 2.
