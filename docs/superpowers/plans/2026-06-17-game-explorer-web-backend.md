# Game Explorer Web Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a localhost-only Python backend that lets the Web console create a validated `game_reverse` run and inspect run/session metadata.

**Architecture:** Keep runtime logic in a testable `game_reverse.web_service` module and HTTP concerns in `game_reverse.web_server`. The server uses only Python standard library HTTP primitives, serves the existing `web/` static files, and exposes a small JSON API. This phase only supports the `game_reverse` runner through dependency injection; Codex and ClaudeCode runners remain planned but unavailable.

**Tech Stack:** Python standard library (`http.server`, `json`, `threading`, `urllib.parse`), existing `game_reverse` config/run loop modules, vanilla JavaScript fetch.

---

## File Structure

- Create `game_reverse/web_service.py`: config validation, run registry, session report loading, runner invocation boundary.
- Create `game_reverse/web_server.py`: localhost HTTP server, static web serving, JSON route dispatch.
- Modify `web/app.js`: try backend APIs first, fall back to `data/sample-run.json`; enable start button only when backend is reachable.
- Modify `web/index.html`: add stable IDs for backend status and run button.
- Create `tests/test_game_reverse_web_service.py`: unit tests for service behavior with fake runner.
- Create `tests/test_game_reverse_web_server.py`: HTTP handler tests against localhost with fake service.

## Task 1: Web Service Tests

**Files:**
- Create: `tests/test_game_reverse_web_service.py`

- [ ] **Step 1: Write failing tests**

Create tests that assert:

```python
# -*- coding: utf-8 -*-
"""Tests for the local game_reverse web service."""

import json
import os
import tempfile
import unittest

from game_reverse.web_service import GameReverseWebService, ValidationError


class FakeRunner:
    def __init__(self):
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        os.makedirs(config.output_root, exist_ok=True)
        session_dir = os.path.join(config.output_root, "fake-session")
        os.makedirs(session_dir, exist_ok=True)
        with open(os.path.join(session_dir, "final_report.md"), "w", encoding="utf-8") as report:
            report.write("# Report\n")
        return session_dir


class TestGameReverseWebService(unittest.TestCase):
    def make_service(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.runner = FakeRunner()
        return GameReverseWebService(output_root=self.tmpdir.name, runner=self.runner)

    def valid_payload(self):
        return {
            "runner": "game_reverse",
            "device_uri": "Android:///emulator-5554",
            "package_name": "com.example.game",
            "max_steps": 2,
            "mission": {
                "type": "free_explore",
                "goal": "Explore tutorial",
                "targets": ["main button"],
                "success_criteria": ["report written"],
            },
            "allowed_actions": ["screenshot", "wait", "back"],
        }

    def test_health_reports_available_runner(self):
        service = self.make_service()

        health = service.health()

        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["runners"][0]["id"], "game_reverse")
        self.assertTrue(health["runners"][0]["available"])

    def test_start_run_validates_and_invokes_game_reverse_runner(self):
        service = self.make_service()

        result = service.start_run(self.valid_payload())

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["runner"], "game_reverse")
        self.assertEqual(len(self.runner.configs), 1)
        self.assertEqual(self.runner.configs[0].package_name, "com.example.game")
        self.assertTrue(os.path.exists(os.path.join(result["session_dir"], "final_report.md")))

    def test_rejects_unknown_runner(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["runner"] = "codex_exec"

        with self.assertRaisesRegex(ValidationError, "runner"):
            service.start_run(payload)

    def test_rejects_tap_without_explicit_opt_in(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["allowed_actions"] = ["screenshot", "wait", "tap"]

        with self.assertRaisesRegex(ValidationError, "enable_unsafe_actions"):
            service.start_run(payload)

    def test_session_report_reads_final_report(self):
        service = self.make_service()
        result = service.start_run(self.valid_payload())

        report = service.session_report(result["id"])

        self.assertEqual(report["id"], result["id"])
        self.assertIn("# Report", report["final_report"])
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service
```

Expected: fail because `game_reverse.web_service` does not exist.

## Task 2: Web Service Implementation

**Files:**
- Create: `game_reverse/web_service.py`

- [ ] **Step 1: Implement minimal service**

Implement:

- `ValidationError(ValueError)`
- `GameReverseWebService(output_root=None, runner=None)`
- `health()`
- `start_run(payload)`
- `get_run(run_id)`
- `list_sessions()`
- `session_report(run_id)`

Validation rules:

- runner must be `game_reverse`
- `package_name` is required
- `max_steps` must be a positive integer
- allowed actions default to `["screenshot", "wait", "back"]`
- `tap` and `swipe` require `enable_unsafe_actions` true

Use existing `GameReverseConfig` and `parse_mission`.

- [ ] **Step 2: Run service tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service
```

Expected: pass.

## Task 3: HTTP Server Tests

**Files:**
- Create: `tests/test_game_reverse_web_server.py`

- [ ] **Step 1: Write failing HTTP tests**

Create tests that start the server on `127.0.0.1` with port `0` and a fake service, then assert:

- `GET /api/health` returns JSON.
- `POST /api/runs` passes payload to fake service and returns JSON.
- `GET /web/index.html` serves the static page.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m unittest tests.test_game_reverse_web_server
```

Expected: fail because `game_reverse.web_server` does not exist.

## Task 4: HTTP Server Implementation

**Files:**
- Create: `game_reverse/web_server.py`

- [ ] **Step 1: Implement standard-library HTTP server**

Implement:

- `create_handler(service=None, web_root=None)`
- `create_server(host="127.0.0.1", port=8765, service=None, web_root=None)`
- `main()` that runs `serve_forever()`

Routes:

- `GET /api/health`
- `GET /api/config`
- `POST /api/runs`
- `GET /api/runs/<id>`
- `GET /api/sessions`
- `GET /api/sessions/<id>/report`
- static files under `/web/`
- redirect `/` to `/web/index.html`

- [ ] **Step 2: Run HTTP tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_web_server
```

Expected: pass.

## Task 5: Web UI Backend Integration

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`

- [ ] **Step 1: Update HTML IDs**

Ensure there is:

- `id="run-state"`
- `id="start-run-button"` on the start button
- `id="backend-status"` near the topbar or sidebar

- [ ] **Step 2: Update JS to use backend when available**

Update `web/app.js` so it:

- calls `fetch("/api/health")`
- if health succeeds, marks backend online, loads static sample for display, and enables the start button
- if health fails, keeps static-only fallback behavior
- on start button click, POSTs current sample config to `/api/runs`
- after a run returns, updates run state and output paths

Do not add Codex/ClaudeCode execution.

- [ ] **Step 3: Update static tests if needed**

Keep `tests/test_web_console_static.py` passing and make sure it still asserts no direct shell execution in JS.

## Task 6: Final Verification And Commit

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor tests.test_game_reverse_config tests.test_game_reverse_journal tests.test_game_reverse_llm_decider tests.test_game_reverse_mission tests.test_game_reverse_report_writer tests.test_game_reverse_run_loop
```

Expected: all tests pass.

- [ ] **Step 2: Smoke run backend**

Run:

```bash
python -m game_reverse.web_server --host 127.0.0.1 --port 8766
```

Open:

```text
http://127.0.0.1:8766/web/index.html
```

Verify the UI loads and backend status can be displayed.

- [ ] **Step 3: Commit**

Commit:

```bash
git add game_reverse/web_service.py game_reverse/web_server.py web/index.html web/app.js tests/test_game_reverse_web_service.py tests/test_game_reverse_web_server.py docs/superpowers/plans/2026-06-17-game-explorer-web-backend.md
git commit -m "Add local web backend for game explorer"
```
