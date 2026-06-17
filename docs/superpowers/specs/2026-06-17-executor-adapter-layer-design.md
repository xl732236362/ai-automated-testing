# Executor Adapter Layer Design

## Goal

Add a testable executor adapter layer behind the local Web backend so the project can represent multiple runner modes through one service boundary. This phase keeps `game_reverse` as the only live runner and adds non-executing `codex_exec` and `claude_print` adapters for command construction, availability reporting, and event parsing.

## Background

The current Web console can start a validated `game_reverse` run, poll run state, read run events, list sessions, and render reports. The UI also shows `codex_exec` and `claude_print` as planned runner modes, but `game_reverse.web_service` still hard-codes runner metadata and rejects any runner that is not `game_reverse`.

The next architectural step is to move runner-specific behavior behind explicit adapters. This gives the backend a controlled place to later add real Codex and ClaudeCode CLI execution without making the browser or web service a generic shell launcher.

## Scope

This phase includes:

- A small adapter registry used by `GameReverseWebService`.
- A live `game_reverse` adapter that delegates to the existing `run_loop` boundary.
- A disabled `codex_exec` adapter that can build the intended `codex exec` argument list and parse fake JSONL events.
- A disabled `claude_print` adapter that can build the intended `claude -p` argument list and parse fake stream-json events.
- Unified runner metadata for `web_service.health()`.
- Clear validation errors when a disabled runner is requested.
- Unit tests for registry behavior, command argument construction, and event parsing.

This phase does not include:

- Starting real `codex` or `claude` processes.
- Streaming real subprocess output to the browser.
- Stop/cancel endpoints.
- WebSocket or Server-Sent Events.
- Browser-side secret editing.
- Remote network binding.
- Generic shell command execution.

## Architecture

Add a focused module:

```text
game_reverse/executors.py
```

The module owns runner metadata, adapter lookup, command construction helpers, and parser functions for the planned external runner output formats.

`game_reverse.web_service.GameReverseWebService` will receive an optional `executors` registry. If none is provided, it creates a default registry containing:

- `game_reverse`: available, starts the existing Python run loop through the current injected runner boundary.
- `codex_exec`: unavailable, constructs command arguments and parses events only.
- `claude_print`: unavailable, constructs command arguments and parses events only.

The service remains responsible for run IDs, background threads, run records, event storage, session listing, and report loading. The adapters remain responsible only for runner-specific metadata and launch/parsing details.

## Adapter Contract

Each adapter exposes these fields or methods:

```python
class ExecutorAdapter:
    id: str
    name: str
    available: bool
    description: str

    def metadata(self) -> dict:
        ...

    def start(self, config, payload):
        ...
```

The exact implementation can use a base class, dataclass, or simple concrete classes. The important contract is behavior:

- `metadata()` returns browser-safe runner data only.
- `start(config, payload)` either starts the adapter-specific run or raises `ValidationError` when unavailable.
- Disabled adapters must not invoke subprocess APIs.

For `game_reverse`, `start()` calls the injected Python runner with a validated `GameReverseConfig` and returns the session directory.

For `codex_exec` and `claude_print`, `start()` raises `ValidationError("runner is not available")` in this phase.

## Command Argument Construction

External runner command construction must return argument lists, not shell strings.

For Codex:

```python
["codex", "exec", "--cd", repo_root, "--json", prompt]
```

For ClaudeCode:

```python
["claude", "-p", "--output-format", "stream-json", prompt]
```

`repo_root` defaults to the repository root and must stay inside the current project unless a later explicit design changes that. The prompt is built from the mission payload and should be a plain string argument, not shell-interpolated text.

## Event Model

Adapters parse external output into the same event shape used by the Web service run log:

```json
{
  "type": "runner_event",
  "source": "codex_exec",
  "message": "short human-readable summary",
  "raw": {}
}
```

Parser behavior:

- Invalid JSON lines become `runner_parse_error` events with the original line in `raw`.
- Empty lines are ignored.
- Recognized status/message fields are mapped to concise `message` text.
- Raw event data is kept for debugging, but no environment variables or secrets are added.

The service-owned lifecycle events remain unchanged:

- `run_queued`
- `run_started`
- `run_completed`
- `run_failed`

## Web Service Changes

`GameReverseWebService.health()` will get runner metadata from the registry instead of hard-coded lists.

`GameReverseWebService.start_run(payload)` will:

1. Read `payload["runner"]`, defaulting to `game_reverse`.
2. Look up the adapter in the registry.
3. Reject unknown runners with `ValidationError("runner")`.
4. Reject disabled runners with `ValidationError("runner is not available")`.
5. Build the existing validated `GameReverseConfig`.
6. Start the selected adapter in the existing background thread path.

The current behavior for safe action validation stays in the service:

- `tap` and `swipe` still require `enable_unsafe_actions`.
- The default runnable Web payload still uses only `screenshot`, `wait`, and `back`.

## Safety Constraints

The browser never constructs or executes commands.

The Python backend must not:

- Accept arbitrary command names or shell fragments from the browser.
- Pass request payload values through a shell.
- Expose `.env`, API keys, or host environment values in runner metadata or events.
- Mark `codex_exec` or `claude_print` available by default.
- Bind outside localhost as part of this phase.

The external adapters are intentionally disabled until a later phase explicitly designs real process lifecycle, environment propagation, cancellation, and output streaming.

## Testing

Add focused unit tests:

- Registry lists `game_reverse`, `codex_exec`, and `claude_print`.
- `game_reverse` metadata is available.
- `codex_exec` and `claude_print` metadata is unavailable.
- `web_service.health()` reflects registry metadata.
- Starting `codex_exec` or `claude_print` returns a validation error and does not invoke subprocess APIs.
- Codex command builder returns the expected argument list.
- ClaudeCode command builder returns the expected argument list.
- Codex JSONL parser maps fake JSON lines into normalized events.
- ClaudeCode stream-json parser maps fake JSON lines into normalized events.
- Invalid JSON parser input produces `runner_parse_error`.
- Existing `game_reverse` web service and web server tests still pass.

## Future Work

A later phase can add real process execution once these additional design choices are made:

- How the operator opts in to external CLI execution.
- How CLI availability is detected.
- Which environment variables are inherited.
- How long-running processes are cancelled.
- How stdout/stderr are persisted.
- Whether process events are polled, streamed with SSE, or exposed through WebSocket.
- How to redact secrets from raw event data.
