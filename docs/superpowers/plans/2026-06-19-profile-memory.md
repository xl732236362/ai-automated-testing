# Profile Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 4 profile memory so learned state maps, affordances, safety rules, and append-only memory are persisted per app and loaded on later runs.

**Architecture:** Add `game_reverse.memory` as the profile persistence boundary. Keep run artifacts immutable under session directories while writing profile files under `game_reverse/profiles/<app_id>/` or a config-provided profile root. The first version loads profile metadata at run start and atomically writes state/affordance/safety/memory artifacts after safe successful steps.

**Tech Stack:** Python standard library, JSON/JSONL artifacts, atomic `os.replace`, existing `unittest`/`pytest` tests, existing `game_reverse` runner and config model.

---

## File Structure

- Create `game_reverse/memory.py`: profile id sanitization, profile directory creation, JSON/JSONL load/update helpers, and profile schema versioning.
- Create `tests/test_game_reverse_memory.py`: unit tests for create/load/update/migration basics and atomic JSON writes.
- Modify `game_reverse/config.py`: add `profile_root` and `profile_enabled` config fields.
- Modify `tests/test_game_reverse_config.py`: verify defaults and config overrides.
- Modify `game_reverse/run_loop.py`: load profile at run start, append memory events, write state map/affordances/safety rules to profile after successful steps.
- Modify `tests/test_game_reverse_run_loop.py`: verify a second run loads prior profile states/affordances and profile files remain readable.

---

### Task 1: Profile Store Core

**Files:**
- Create: `game_reverse/memory.py`
- Test: `tests/test_game_reverse_memory.py`

- [ ] **Step 1: Write failing memory tests**

Add tests for:

- `ProfileStore(root, app_id)` creates `profile.json`, `state_map.json`, `affordances.json`, `safety_rules.json`, and `memory.jsonl`
- app ids are safely sanitized into directory names
- `update_json()` writes readable JSON and can be loaded
- `append_memory()` appends JSONL events
- older or missing profile schema is migrated to current version

- [ ] **Step 2: Verify tests fail for missing module**

Run:

```bash
python -m pytest tests/test_game_reverse_memory.py -q
```

Expected: FAIL with missing `game_reverse.memory`.

- [ ] **Step 3: Implement profile store**

Implement:

```python
PROFILE_SCHEMA_VERSION = 1

class ProfileStore:
    def __init__(self, root, app_id): ...
    def initialize(self, package_name=None): ...
    def load_json(self, filename, default): ...
    def update_json(self, filename, payload): ...
    def append_memory(self, event): ...
```

Use temp files plus `os.replace()` for JSON updates.

- [ ] **Step 4: Verify memory tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_memory.py -q
```

Expected: PASS.

---

### Task 2: Config Support

**Files:**
- Modify: `game_reverse/config.py`
- Modify: `tests/test_game_reverse_config.py`

- [ ] **Step 1: Write failing config tests**

Assert default `profile_root == "game_reverse/profiles"` and `profile_enabled is True`. Assert JSON config can set `profile_root` and `profile_enabled`.

- [ ] **Step 2: Implement config fields**

Add dataclass fields and loader support.

- [ ] **Step 3: Verify config tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_config.py -q
```

Expected: PASS.

---

### Task 3: Run Loop Profile Integration

**Files:**
- Modify: `game_reverse/run_loop.py`
- Modify: `tests/test_game_reverse_run_loop.py`

- [ ] **Step 1: Write failing run-loop profile test**

Run `run_loop()` twice with the same temp `profile_root` and package. First run creates state/affordance artifacts. Second run should load prior profile metadata and preserve/update the same profile files. Assert:

- `profiles/com.example.game/profile.json` exists
- profile `state_map.json`, `affordances.json`, `safety_rules.json`, and `memory.jsonl` exist
- `memory.jsonl` has events from both runs
- profile JSON files parse cleanly

- [ ] **Step 2: Implement profile integration**

At run start:

- create `ProfileStore` when profile is enabled
- initialize profile
- load existing state/affordance JSON for context events and memory event

After successful steps:

- update `state_map.json`
- update `affordances.json`
- update `safety_rules.json` with sensitive state evidence
- append memory event containing observation, action, feedback, transition, and session name

- [ ] **Step 3: Verify run-loop tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

---

### Task 4: Phase 4 Acceptance Verification and Commit

- [ ] **Step 1: Run focused Phase 4 tests**

Run:

```bash
python -m pytest tests/test_game_reverse_memory.py tests/test_game_reverse_config.py tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full game_reverse regression suite**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_affordances.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_config.py tests/test_game_reverse_executors.py tests/test_game_reverse_feedback.py tests/test_game_reverse_journal.py tests/test_game_reverse_lightweight_runner.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_memory.py tests/test_game_reverse_mission.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_state_graph.py tests/test_game_reverse_target_discovery.py tests/test_game_reverse_web_server.py tests/test_game_reverse_web_service.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit Phase 4**

Run:

```bash
git add docs/superpowers/plans/2026-06-19-profile-memory.md game_reverse/config.py game_reverse/memory.py game_reverse/run_loop.py tests/test_game_reverse_config.py tests/test_game_reverse_memory.py tests/test_game_reverse_run_loop.py
git commit -m "feat: persist explorer profile memory"
```
