# Game Explorer Web Console Design

## Goal

Build a local Web UI for configuring and observing App/Game exploration tasks in this repository. The UI should help an operator use the existing Airtest and `game_reverse` workflow with ClaudeCode/Codex-assisted exploration, without requiring the operator to edit JSON files or inspect session folders manually.

The first implementation is static-first: it creates the real UI shell, form layout, run timeline, and report preview using plain browser files. A later phase can add a local Python backend that starts `game_reverse.run_loop`, `codex exec`, or `claude -p` through a controlled executor adapter layer.

## Scope

The first Web UI includes:

- A Chinese operator console for configuring a mission.
- Fields for device URI, package name, mission type, mission goal, targets, success criteria, model, allowed actions, max steps, and failure limit.
- A runner selector with `game_reverse`, `codex_exec`, and `claude_print` as planned executor modes.
- A live-run layout with latest screenshot, decision timeline, action log, risk notes, and output paths.
- A report preview area for `mission_draft.md` and `final_report.md`.
- Static sample data that mirrors the current `game_reverse` records.

The first Web UI does not execute commands, connect to devices, store secrets, or mutate project files.

## User Experience

The console opens directly into the working surface, not a landing page.

The primary page has three zones:

1. Left navigation: Run Mission, Device Setup, Mission Presets, Sessions, Reports, Settings.
2. Main workspace: mission configuration at the top, run controls below, and a decision timeline for exploration steps.
3. Right inspector: latest screenshot preview, current finding draft, risk notes, and output files.

The interface language is Chinese. Technical identifiers such as `device_uri`, `package_name`, `codex exec`, and file paths remain visible where they help the operator map UI fields to project configuration.

## Visual Direction

The console should feel like a practical test operations tool:

- Dense but readable layout.
- Neutral surface colors with restrained accents.
- Small, stable controls sized for repeated use.
- No marketing hero, decorative gradients, or card-heavy landing page.
- Screenshots and run state are first-class, because the operator needs to inspect what the agent saw and did.

## Static File Structure

The initial implementation should use plain static files:

```text
web/
  index.html
  styles.css
  app.js
  data/sample-run.json
```

No frontend build tool is required for the first version. Opening `web/index.html` in a browser should work.

## Future Backend Boundary

The future backend should be a local-only Python service, for example:

```text
python -m game_reverse.web_server
```

It should expose a small API:

```text
GET  /api/health
GET  /api/config
POST /api/config
POST /api/runs
GET  /api/runs/{id}
GET  /api/runs/{id}/events
POST /api/runs/{id}/stop
GET  /api/sessions
GET  /api/sessions/{id}/report
```

The browser never invokes Codex, ClaudeCode, Airtest, ADB, or shell commands directly.

## Executor Adapter Layer

The backend should call external tools only through explicit executor adapters:

```text
Web UI
  -> Local Python backend
    -> Executor adapter
      -> game_reverse.run_loop
      -> codex exec
      -> claude -p
      -> Airtest / ADB / emulator
```

Planned adapters:

- `game_reverse`: calls the current Python `run_loop` with a validated config object.
- `codex_exec`: starts `codex exec --cd <repo> --json <prompt>` and streams JSONL events.
- `claude_print`: starts `claude -p --output-format stream-json <prompt>` and streams JSON events.

The UI should present these as runner modes, but the static version should mark them as planned integrations rather than live actions.

## Safety Constraints

The backend phase must enforce these constraints:

- Bind to localhost by default.
- Never send `.env` values or API keys to the browser.
- Keep all command execution inside the current repository unless explicitly configured.
- Validate `device_uri`, `package_name`, `mission.type`, `max_steps`, and `allowed_actions`.
- Default to safe actions: screenshot, wait, back.
- Require explicit opt-in for tap and swipe.
- Treat login, real-name verification, payment, permission grants, account/password entry, and other sensitive screens as wait/back-only states.
- Log failed steps with error type and reason.
- Write run outputs under `game_reverse/outputs/sessions`.

## Data Model

The static UI should use sample data shaped like current runtime records:

```json
{
  "config": {
    "device_uri": "Android:///emulator-5554",
    "package_name": "com.example.game",
    "mission": {
      "type": "free_explore",
      "goal": "探索新手引导流程，识别核心玩法循环。",
      "targets": [],
      "success_criteria": []
    },
    "model": "claude-opus-4-8",
    "allowed_actions": ["screenshot", "wait", "back", "tap", "swipe"],
    "max_steps": 50,
    "consecutive_failure_limit": 3
  },
  "run": {
    "id": "sample",
    "status": "idle",
    "steps": [
      {
        "step": 1,
        "state": "home",
        "screen_summary": "识别到新手引导主页。",
        "action": {"type": "wait", "seconds": 1},
        "reason": "等待界面稳定。",
        "result": "ok",
        "risks": []
      }
    ],
    "outputs": {
      "session_dir": "game_reverse/outputs/sessions/sample",
      "mission_draft": "mission_draft.md",
      "final_report": "final_report.md"
    }
  }
}
```

## Testing

For the static phase:

- Add lightweight Python tests that assert the expected static files exist.
- Verify `index.html` references `styles.css`, `app.js`, and `data/sample-run.json`.
- Verify the sample JSON contains required config and run fields.
- Manually open `web/index.html` or serve it with a simple local server to inspect layout.

For the backend phase:

- Test config validation separately from process launching.
- Unit-test executor command construction without starting external tools.
- Use fake process streams to test event parsing for `codex exec --json` and `claude -p --output-format stream-json`.
- Keep real emulator/device tests as manual smoke tests.

## Open Decisions

The first implementation should proceed with the static phase only. Backend command execution, process cancellation, real-time event streaming, and session browsing should be implemented after the operator console layout is validated in the browser.
