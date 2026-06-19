# Web Console Profile Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only learned profile viewer to the local web console so operators can inspect current states, transitions, affordances, skills, safety rules, goals, and recent action reasoning.

**Architecture:** Add a focused profile summarizer that reads existing profile JSON/JSONL artifacts without mutating them. Expose the summary through the existing local web service and HTTP server, then render the data in the current static console as compact tables/lists in the inspector column.

**Tech Stack:** Python standard library, existing `GameReverseWebService` and `ThreadingHTTPServer`, static HTML/CSS/JS, existing `unittest`/`pytest` tests.

---

## File Structure

- Create `game_reverse/profile_view.py`: read profile artifacts and normalize a UI/API summary.
- Create `tests/test_game_reverse_profile_view.py`: unit tests for profile summary shape.
- Modify `game_reverse/web_service.py`: accept `profile_root`, expose `profile_summary(package_name)`, include profile root in config.
- Modify `game_reverse/web_server.py`: add `GET /api/profiles/<package_name>`.
- Modify `tests/test_game_reverse_web_service.py`: verify service profile summary.
- Modify `tests/test_game_reverse_web_server.py`: verify HTTP endpoint shape.
- Modify `web/index.html`: add a learned profile inspector section and navigation link.
- Modify `web/app.js`: fetch and render profile summary; render session action reasoning from loaded report artifacts.
- Modify `web/styles.css`: add compact profile list/table styles.
- Modify `web/data/sample-run.json`: add static profile sample data.
- Modify `tests/test_web_console_static.py`: verify static wiring.

---

### Task 1: Profile Summary Reader

**Files:**
- Create: `game_reverse/profile_view.py`
- Create: `tests/test_game_reverse_profile_view.py`

- [x] **Step 1: Write failing profile summary tests**

Add tests that create a temporary profile directory containing `state_map.json`, `affordances.json`, `skills.json`, `safety_rules.json`, `goals.json`, and `memory.jsonl`, then assert `load_profile_summary(root, package_name)` returns:

- `exists: True`
- a newest `current_state`
- sorted transitions
- flattened affordances with confidence and last result
- skills with confidence
- safety interventions
- goals
- recent memory events

- [x] **Step 2: Verify tests fail for missing module**

Run:

```bash
python -m pytest tests/test_game_reverse_profile_view.py -q
```

Expected: FAIL with missing `game_reverse.profile_view`.

- [x] **Step 3: Implement profile summary reader**

Implement:

```python
def load_profile_summary(profile_root, package_name):
    ...
```

Use `sanitize_app_id()` from `game_reverse.memory`, read missing artifacts as empty defaults, sort states by `last_seen_step` descending, sort affordances by confidence descending, and return an `exists: False` empty shape when the profile directory does not exist.

- [x] **Step 4: Verify reader tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_profile_view.py -q
```

Expected: PASS.

---

### Task 2: Web API Endpoint

**Files:**
- Modify: `game_reverse/web_service.py`
- Modify: `game_reverse/web_server.py`
- Modify: `tests/test_game_reverse_web_service.py`
- Modify: `tests/test_game_reverse_web_server.py`

- [x] **Step 1: Write failing service/server tests**

Add tests that:

- construct `GameReverseWebService(profile_root=tmpdir)` and assert `profile_summary("com.example.game")` includes `current_state`, `affordances`, `skills`, `safety`, `goals`, and `memory_summary`
- call `GET /api/profiles/com.example.game` through the HTTP server and assert the returned package name and current state id

- [x] **Step 2: Verify tests fail for missing API**

Run:

```bash
python -m pytest tests/test_game_reverse_web_service.py::TestGameReverseWebService::test_profile_summary_exposes_learned_profile tests/test_game_reverse_web_server.py::TestGameReverseWebServer::test_profile_endpoint_returns_json -q
```

Expected: FAIL because the service method and route are missing.

- [x] **Step 3: Implement API integration**

Add `profile_root` to `GameReverseWebService.__init__`, expose it from `config()`, pass it into `GameReverseConfig`, add `profile_summary()`, and route `/api/profiles/<package_name>` in `web_server.py`.

- [x] **Step 4: Verify API tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_profile_view.py tests/test_game_reverse_web_service.py tests/test_game_reverse_web_server.py -q
```

Expected: PASS.

---

### Task 3: Static Console Viewer

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `web/data/sample-run.json`
- Modify: `tests/test_web_console_static.py`

- [x] **Step 1: Write failing static UI tests**

Assert the HTML includes `id="profile-summary"`, `id="profile-current-state"`, `id="profile-affordances"`, `id="profile-skills"`, `id="profile-safety"`, and `id="action-reasoning"`. Assert the JS contains `loadProfileSummary`, `/api/profiles/`, `renderProfileSummary`, `renderActionReasoning`, and safe fallback handling for missing profiles.

- [x] **Step 2: Verify tests fail for missing UI wiring**

Run:

```bash
python -m pytest tests/test_web_console_static.py -q
```

Expected: FAIL because the profile viewer IDs and functions are missing.

- [x] **Step 3: Implement UI wiring**

Add a compact "Profile" inspector section, fetch the profile summary after sample/backend load and after report load, render current state, transitions, affordances, skills, safety interventions, goals, and latest action reasoning. Use only read-only DOM updates and keep controls unchanged.

- [x] **Step 4: Verify static UI tests pass**

Run:

```bash
python -m pytest tests/test_web_console_static.py -q
```

Expected: PASS.

---

### Task 4: Phase 7 Acceptance Verification and Commit

- [x] **Step 1: Run focused regression**

Run:

```bash
python -m pytest tests/test_game_reverse_profile_view.py tests/test_game_reverse_web_service.py tests/test_game_reverse_web_server.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [x] **Step 2: Run full game_reverse regression suite**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_affordances.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_config.py tests/test_game_reverse_executors.py tests/test_game_reverse_feedback.py tests/test_game_reverse_goal_planner.py tests/test_game_reverse_journal.py tests/test_game_reverse_lightweight_runner.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_memory.py tests/test_game_reverse_mission.py tests/test_game_reverse_profile_view.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_skill_library.py tests/test_game_reverse_state_graph.py tests/test_game_reverse_target_discovery.py tests/test_game_reverse_web_server.py tests/test_game_reverse_web_service.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [x] **Step 3: Commit Phase 7**

Run:

```bash
git add docs/superpowers/plans/2026-06-19-web-console-profile-viewer.md game_reverse/profile_view.py game_reverse/web_service.py game_reverse/web_server.py web/index.html web/app.js web/styles.css web/data/sample-run.json tests/test_game_reverse_profile_view.py tests/test_game_reverse_web_service.py tests/test_game_reverse_web_server.py tests/test_web_console_static.py
git commit -m "feat: add web profile viewer"
```
