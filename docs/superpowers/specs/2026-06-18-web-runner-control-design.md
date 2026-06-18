# Web Runner Control Design

## Goal

Make the existing local Web console able to select an available runner, start `codex_exec` through the existing backend API, and inspect run events and final reports without using PowerShell commands.

## Background

The backend can already run:

- `game_reverse`: in-process Python runner.
- `codex_exec`: opt-in real Codex CLI runner.
- `claude_print`: planned runner, still unavailable.

The current Web console shows runner cards but the start button always sends `runner: "game_reverse"`. Several UI strings also render as mojibake because earlier edits preserved incorrectly decoded Chinese text.

## Scope

This phase includes:

- Runner selection in the Web UI.
- Runner availability from `/api/health`.
- Editable mission fields needed to start practical runs.
- Start payload using the selected runner.
- Event rendering that shows runner messages, errors, and session paths.
- Final report loading after completion.
- Chinese UI text cleanup for touched static files.
- Static tests and browser smoke verification.

This phase does not include:

- New backend endpoints.
- WebSocket or Server-Sent Events.
- Enabling `tap` or `swipe` from the UI.
- Editing environment variables from the browser.
- Running arbitrary commands from the browser.
- Real ClaudeCode execution.

## UI Behavior

The Runner panel becomes an interactive selection surface:

- Available runners are selectable buttons/cards.
- Unavailable runners are disabled and show their backend description.
- The selected runner is visually distinct.
- `codex_exec` can be selected only when `/api/health` reports `available: true`.
- If no backend is online, the UI falls back to sample data and disables start.

The Mission panel allows editing:

- `device_uri`
- `package_name`
- `model`
- `max_steps`
- `mission.goal`

The action list stays read-only in this phase:

- `screenshot`
- `wait`
- `back`

The start button text and status message reference the selected runner.

## Data Flow

On load:

1. Load `web/data/sample-run.json`.
2. Call `/api/health`.
3. If health succeeds, merge backend runner metadata into `currentData.runners`.
4. Select the first available runner, preferring `game_reverse`.
5. Render mission, config, runners, actions, events, sessions, and report preview.

On start:

1. Read editable fields from the DOM.
2. Build payload:

```json
{
  "runner": "codex_exec",
  "device_uri": "Android:///emulator-5554",
  "package_name": "com.example.game",
  "max_steps": 2,
  "mission": {
    "type": "free_explore",
    "goal": "..."
  },
  "model": "...",
  "allowed_actions": ["screenshot", "wait", "back"],
  "enable_unsafe_actions": false
}
```

3. POST `/api/runs`.
4. Poll `/api/runs/<id>`.
5. Poll `/api/runs/<id>/events`.
6. On completion, call `/api/sessions/<id>/report`.

## Error Handling

- Unknown backend errors render in the run status badge and event log.
- Unavailable selected runner disables the start button.
- Failed runs keep the event log visible and show `run.error`.
- Report loading failures render in the report preview instead of crashing the page.
- Empty event lists show a Chinese empty state.

## Safety

The browser never sends shell commands.

The browser never edits:

- `GAME_REVERSE_*` environment variables.
- Codex command path.
- Codex sandbox.
- API keys.

The UI sends `enable_unsafe_actions: false` and safe actions only. Real device actions remain backend-gated.

## Testing

Add or update tests in `tests/test_web_console_static.py`:

- Static HTML includes editable control IDs.
- App script declares selected runner state.
- App script sends `runner: selectedRunnerId`.
- App script never references `child_process`, `codex exec`, or `claude -p`.
- Sample data includes runner metadata and safe actions.
- Chinese labels appear correctly in touched UI files.

Verification commands:

```text
python -m unittest tests.test_web_console_static
node --check web/app.js
```

Browser smoke:

1. Start backend with `GAME_REVERSE_ENABLE_CODEX_EXEC=1`.
2. Open `http://127.0.0.1:8768/web/index.html`.
3. Confirm runner cards reflect backend availability.
4. Select `codex_exec`.
5. Start a read-only smoke task.
6. Confirm events and final report appear.
