# Game Explorer Live Run Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Web console usable for real `game_reverse` runs by starting runs in the background, polling run/session state, and viewing generated reports without blocking the HTTP server.

**Architecture:** Replace the current synchronous `/api/runs` behavior with a small in-memory background run registry in `game_reverse.web_service`. The HTTP server stays standard-library based and exposes pollable JSON endpoints. The Web UI uses the existing static sample as fallback, but when the backend is online it can start a safe run, poll status, list sessions, and render report content.

**Tech Stack:** Python standard library (`threading`, `queue`-style event list, `http.server`), existing `game_reverse` modules, vanilla JavaScript polling with `fetch`.

---

## Scope

This phase should implement:

- Background `game_reverse` run execution so `/api/runs` returns immediately.
- Run status values: `queued`, `running`, `completed`, `failed`.
- Pollable endpoints for run state and run events.
- Session listing from `game_reverse/outputs/sessions`.
- Report retrieval by session id.
- Web UI wiring for start, polling, session list, and report preview.
- A safe-run payload path that defaults to `screenshot`, `wait`, and `back`.

This phase should not implement:

- `codex exec` runner.
- `claude -p` runner.
- WebSocket/SSE streaming.
- Multi-user auth.
- Remote network binding.
- Secret editing in the browser.

## File Structure

- Modify `game_reverse/web_service.py`: background run registry, events, safe payload builder, session lookup by id.
- Modify `game_reverse/web_server.py`: expose `/api/runs/<id>/events`, improve session report route, return consistent JSON errors.
- Modify `web/app.js`: build payload from current UI/sample data, start run, poll status/events, render report/session outputs.
- Modify `web/index.html`: add session list and event log containers if missing.
- Modify `web/styles.css`: style event log and session list.
- Add/modify `tests/test_game_reverse_web_service.py`: background behavior and events.
- Add/modify `tests/test_game_reverse_web_server.py`: events/report endpoints.
- Add/modify `tests/test_web_console_static.py`: assert new UI hooks exist and JS still does not directly invoke shell commands.

## Task 1: Background Service Contract

**Files:**
- Modify: `tests/test_game_reverse_web_service.py`
- Modify: `game_reverse/web_service.py`

- [ ] **Step 1: Add failing service tests**

Add tests for:

```python
class SlowFakeRunner:
    def __init__(self):
        self.started = False
        self.release = threading.Event()

    def __call__(self, config):
        self.started = True
        self.release.wait(timeout=5)
        session_dir = os.path.join(config.output_root, "slow-session")
        os.makedirs(session_dir, exist_ok=True)
        with open(os.path.join(session_dir, "final_report.md"), "w", encoding="utf-8") as report:
            report.write("# Slow Report\n")
        return session_dir
```

Assertions:

- `start_run(payload)` returns with status `queued` or `running` before the fake runner finishes.
- `get_run(run_id)` eventually reports `running`.
- `run_events(run_id)` contains a `run_started` event.
- after releasing the runner, `get_run(run_id)` eventually reports `completed`.
- `session_report(run_id)` reads `# Slow Report`.

- [ ] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service
```

Expected: fail because `run_events` and background behavior do not exist.

- [ ] **Step 3: Implement background run registry**

Update `GameReverseWebService`:

- use `threading.Lock`
- create run records before starting a thread
- append events like `run_queued`, `run_started`, `run_completed`, `run_failed`
- start `threading.Thread(target=self._run_background, args=(run_id, config), daemon=True)`
- return immediately from `start_run`
- add `run_events(run_id)`

- [ ] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service
```

Expected: pass.

## Task 2: HTTP Polling Endpoints

**Files:**
- Modify: `tests/test_game_reverse_web_server.py`
- Modify: `game_reverse/web_server.py`

- [ ] **Step 1: Add failing HTTP tests**

Add tests for:

- `GET /api/runs/fake-run/events`
- `GET /api/sessions/fake-run/report`
- JSON error shape for missing run.

Expected event response:

```json
{"id": "fake-run", "events": [{"type": "run_started"}]}
```

- [ ] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_web_server
```

Expected: fail because events route is not implemented or fake service contract is incomplete.

- [ ] **Step 3: Implement routes**

Update `web_server`:

- route `GET /api/runs/<id>/events` before generic `GET /api/runs/<id>`
- return `{"id": run_id, "events": service.run_events(run_id)}`
- keep `/api/sessions/<id>/report`
- return JSON errors consistently.

- [ ] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_web_server
```

Expected: pass.

## Task 3: Web UI Live Run Wiring

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `tests/test_web_console_static.py`

- [ ] **Step 1: Add UI hook tests**

Update static tests to assert:

- `id="event-log"` exists.
- `id="session-list"` exists.
- `app.js` contains `pollRun`.
- `app.js` contains `/api/runs/`.
- `app.js` still does not contain `child_process`, `codex exec`, or `claude -p`.

- [ ] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: fail because UI hooks and polling do not exist.

- [ ] **Step 3: Add UI containers**

Add:

```html
<div class="event-log" id="event-log"></div>
<div class="session-list" id="session-list"></div>
```

Place event log below timeline and session list in the right inspector or reports area.

- [ ] **Step 4: Implement polling in JS**

Add:

- `startRun()`
- `pollRun(runId)`
- `loadRunEvents(runId)`
- `loadSessions()`
- `loadReport(sessionId)`
- `renderEvents(events)`
- `renderSessions(sessions)`

Rules:

- Poll every 1000 ms while status is `queued` or `running`.
- Stop polling on `completed` or `failed`.
- On completed, load report and update output panel.
- On failed, show error in run state.

- [ ] **Step 5: Style event/session panels**

Add compact list styles for event log and session list. Ensure mobile layout still stacks cleanly.

- [ ] **Step 6: Run GREEN**

Run:

```bash
python -m unittest tests.test_web_console_static
node --check web/app.js
```

Expected: pass.

## Task 4: Safe Real Run Preset

**Files:**
- Modify: `web/data/sample-run.json`
- Modify: `web/app.js`
- Modify: `tests/test_web_console_static.py`

- [ ] **Step 1: Add failing test for safe default**

Update `tests/test_web_console_static.py` to assert:

- sample config default `allowed_actions` contains only `screenshot`, `wait`, `back`
- `enable_unsafe_actions` is not true in the default start payload path.

- [ ] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: fail because current sample data includes `tap` and `swipe`.

- [ ] **Step 3: Make the sample payload safe**

Update `web/data/sample-run.json`:

```json
"allowed_actions": ["screenshot", "wait", "back"]
```

Keep UI copy explaining tap/swipe as later opt-in actions, but do not include them in the default runnable payload.

- [ ] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: pass.

## Task 5: Manual Smoke With Backend

**Files:**
- No code changes unless smoke finds a bug.

- [ ] **Step 1: Run tests**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor tests.test_game_reverse_config tests.test_game_reverse_journal tests.test_game_reverse_llm_decider tests.test_game_reverse_mission tests.test_game_reverse_report_writer tests.test_game_reverse_run_loop
```

Expected: all pass.

- [ ] **Step 2: Start backend**

Run:

```bash
python -m game_reverse.web_server --host 127.0.0.1 --port 8767
```

Open:

```text
http://127.0.0.1:8767/web/index.html
```

- [ ] **Step 3: Smoke without emulator side effects**

Use a test payload or fake runner in unit tests for automation. For manual UI, verify:

- backend online badge appears
- start button is enabled
- clicking start with real runner is only done after MuMu/device/API env are intentionally ready

## Task 6: Commit

**Files:**
- All changed files from Tasks 1-4.

- [ ] **Step 1: Final checks**

Run:

```bash
git diff --check
git status --short
```

- [ ] **Step 2: Commit**

Commit:

```bash
git add game_reverse/web_service.py game_reverse/web_server.py web/index.html web/styles.css web/app.js web/data/sample-run.json tests/test_game_reverse_web_service.py tests/test_game_reverse_web_server.py tests/test_web_console_static.py docs/superpowers/plans/2026-06-17-game-explorer-live-run-observation.md
git commit -m "Plan live run observation for game explorer"
```
