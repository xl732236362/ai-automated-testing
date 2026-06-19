# Skill Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 5 skill library support so reusable multi-step action sequences can be represented, matched, replayed with validation, recorded, mined from successful traces, and updated by success/failure.

**Architecture:** Add `game_reverse.skill_library` as the deterministic skill boundary. The module stores skill records as JSON-serializable dictionaries, matches trigger state labels/affordances, replays steps through existing action validation/execution, and updates confidence. The run loop integrates high-confidence skill attempts before LLM decisions and falls back to exploration when no skill matches or replay fails.

**Tech Stack:** Python standard library, JSON/JSONL artifacts, existing `validate_action`, existing executor API, `unittest`/`pytest`.

---

## File Structure

- Create `game_reverse/skill_library.py`: skill schema helpers, matching, replay, mining, confidence updates, and serializable store.
- Create `tests/test_game_reverse_skill_library.py`: unit tests for matching, replay success/failure, confidence updates, and simple mining.
- Modify `game_reverse/journal.py`: add `skill_attempts.jsonl` writer.
- Modify `tests/test_game_reverse_journal.py`: verify skill attempts JSONL.
- Modify `game_reverse/memory.py`: initialize `skills.json`.
- Modify `tests/test_game_reverse_memory.py`: verify profile includes `skills.json`.
- Modify `game_reverse/run_loop.py`: load profile skills, attempt high-confidence skills before LLM decisions, record attempts, and persist skills.
- Modify `tests/test_game_reverse_run_loop.py`: verify matched skill is executed before decider and failure falls back to decider action.

---

### Task 1: Skill Library Core

**Files:**
- Create: `game_reverse/skill_library.py`
- Test: `tests/test_game_reverse_skill_library.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

- skill matches when current observation state label is in trigger labels
- skill does not match under confidence threshold
- replay validates and executes each step
- failed replay decreases confidence and returns failure attempt
- successful replay increases confidence and returns success attempt
- mining creates a candidate skill from a successful trace ending in `level_started` or `popup_closed`

- [ ] **Step 2: Verify tests fail for missing module**

Run:

```bash
python -m pytest tests/test_game_reverse_skill_library.py -q
```

Expected: FAIL with missing `game_reverse.skill_library`.

- [ ] **Step 3: Implement core**

Implement:

```python
class SkillLibrary:
    def __init__(self, skills=None): ...
    def best_match(self, observation, affordances=None): ...
    def replay(self, skill, executor, screen_path, screen_size, allowed_actions): ...
    def record_attempt(self, skill_name, success): ...
    def mine_candidates(self, action_records): ...
    def to_skills(self): ...
```

- [ ] **Step 4: Verify skill tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_skill_library.py -q
```

Expected: PASS.

---

### Task 2: Artifacts and Profile Support

**Files:**
- Modify: `game_reverse/journal.py`
- Modify: `tests/test_game_reverse_journal.py`
- Modify: `game_reverse/memory.py`
- Modify: `tests/test_game_reverse_memory.py`

- [ ] **Step 1: Write failing artifact tests**

Assert `Journal.write_skill_attempt()` writes `skill_attempts.jsonl`, and `ProfileStore.initialize()` creates `skills.json`.

- [ ] **Step 2: Implement artifact support**

Add journal JSONL writer and profile `skills.json` default:

```json
{"version": 1, "skills": []}
```

- [ ] **Step 3: Verify tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py -q
```

Expected: PASS.

---

### Task 3: Run Loop Integration

**Files:**
- Modify: `game_reverse/run_loop.py`
- Modify: `tests/test_game_reverse_run_loop.py`

- [ ] **Step 1: Write failing integration tests**

Add a profile with `skills.json` containing a high-confidence skill triggered by `main_menu`. Run loop should execute the skill before calling the decider. Add another test where skill replay raises an executor error; run loop should record failed attempt and continue with decider action.

- [ ] **Step 2: Implement integration**

At run start, load profile skills into `SkillLibrary`. After observation/state update and affordance collection, attempt matching high-confidence skill. If replay succeeds, record a `skill_attempts.jsonl` record, write action/observation with `action_source: "skill"`, update confidence, persist `skills.json`, and skip LLM decision for that step. If replay fails, record failed attempt, persist confidence decrease, then continue to LLM decision.

- [ ] **Step 3: Verify run-loop tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

---

### Task 4: Phase 5 Acceptance Verification and Commit

- [ ] **Step 1: Run focused Phase 5 tests**

Run:

```bash
python -m pytest tests/test_game_reverse_skill_library.py tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py tests/test_game_reverse_run_loop.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full game_reverse regression suite**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_affordances.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_config.py tests/test_game_reverse_executors.py tests/test_game_reverse_feedback.py tests/test_game_reverse_journal.py tests/test_game_reverse_lightweight_runner.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_memory.py tests/test_game_reverse_mission.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_skill_library.py tests/test_game_reverse_state_graph.py tests/test_game_reverse_target_discovery.py tests/test_game_reverse_web_server.py tests/test_game_reverse_web_service.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit Phase 5**

Run:

```bash
git add docs/superpowers/plans/2026-06-19-skill-library.md game_reverse/skill_library.py game_reverse/journal.py game_reverse/memory.py game_reverse/run_loop.py tests/test_game_reverse_skill_library.py tests/test_game_reverse_journal.py tests/test_game_reverse_memory.py tests/test_game_reverse_run_loop.py
git commit -m "feat: add reusable skill library"
```
