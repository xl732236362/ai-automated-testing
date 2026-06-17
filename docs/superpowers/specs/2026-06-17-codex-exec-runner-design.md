# Codex Exec Runner Design

## Goal

Turn the existing disabled `codex_exec` adapter into an opt-in real runner that can launch `codex exec` from the local Web backend, stream JSONL progress into the existing run event model, persist logs under the session output directory, and fail safely on unavailable CLI, timeout, or non-zero process exit.

## Background

The current executor layer already provides:

- `game_reverse`: the live in-process runner.
- `codex_exec`: disabled command/prompt/parser skeleton.
- `claude_print`: disabled command/prompt/parser skeleton.
- `GameReverseWebService`: run IDs, background thread execution, run status, event storage, session listing, and report loading.

This phase builds only the Codex execution path. ClaudeCode remains disabled until a separate phase because its process contract, auth behavior, and stream shape should be verified independently.

Local CLI verification on this machine shows:

```text
codex-cli 0.139.0
codex exec [OPTIONS] [PROMPT]
```

Relevant supported options are `--cd <DIR>`, `--json`, `--output-last-message <FILE>`, `--sandbox <MODE>`, `--profile <PROFILE>`, `--model <MODEL>`, `--config <key=value>`, and `--dangerously-bypass-approvals-and-sandbox`. This design uses the safe subset needed for automation and keeps dangerous options out of browser payload control.

## Considered Approaches

Recommended: make `codex_exec` available only when an explicit environment flag is enabled and the `codex` binary is found. The backend starts `codex exec` with `subprocess.Popen(shell=False)`, drains stdout JSONL into run events, writes stdout/stderr/final message files, and returns the created run directory as the session directory. This keeps process execution narrow and testable.

Alternative 1: keep Codex disabled and only improve command previews. This is safer but does not meet the next objective: letting the project delegate exploration tasks to Codex CLI.

Alternative 2: add a generic external command runner where the browser sends commands. This would be more flexible but creates a larger security boundary than the project needs and makes secret redaction, command validation, and support burden worse.

## Scope

This phase includes:

- Opt-in availability for `codex_exec`.
- CLI discovery using `shutil.which`.
- Real `subprocess.Popen` execution with `shell=False`.
- Service-to-adapter run context so external runners can emit events while running.
- A Codex-specific run directory under the configured output root.
- Captured stdout JSONL, stderr log, final assistant message, and generated `final_report.md`.
- Timeout handling.
- Non-zero exit handling.
- Unit tests with fake processes; tests must not start real Codex.

This phase does not include:

- Real ClaudeCode execution.
- Stop/cancel endpoint.
- Browser-side runner configuration UI beyond the existing runner selector/data model.
- Server-Sent Events or WebSocket streaming.
- Arbitrary command execution.
- Passing API keys or environment variables from browser payload into Codex.
- Enabling dangerous Codex flags from the Web UI.

## Configuration

The default behavior remains safe:

- `codex_exec` is unavailable unless explicitly enabled.
- `game_reverse` remains the only available live runner by default.

Use backend environment variables:

```text
GAME_REVERSE_ENABLE_CODEX_EXEC=1
GAME_REVERSE_CODEX_TIMEOUT_SECONDS=900
GAME_REVERSE_CODEX_COMMAND=codex
GAME_REVERSE_CODEX_SANDBOX=workspace-write
GAME_REVERSE_CODEX_PROFILE=
GAME_REVERSE_CODEX_MODEL=
```

Rules:

- `GAME_REVERSE_ENABLE_CODEX_EXEC=1` is required for availability.
- `GAME_REVERSE_CODEX_COMMAND` defaults to `codex`.
- Availability is true only when the enable flag is set and `shutil.which(command)` resolves a binary.
- Timeout defaults to 900 seconds if unset.
- Sandbox defaults to `workspace-write`.
- Profile and model are omitted when empty.
- Browser payload cannot override command, timeout, sandbox, profile, model, or config flags in this phase.

## Adapter Contract Update

The current adapter method is:

```python
def start(self, config, payload):
    ...
```

Extend it to accept an optional context:

```python
def start(self, config, payload, context=None):
    ...
```

Add a focused context object in `game_reverse.executors`:

```python
@dataclass
class ExecutorRunContext:
    run_id: str
    run_dir: str
    emit_event: object
```

`emit_event(event_type, **extra)` appends a Web-service run event for the active run. `GameReverseExecutor` ignores the context and preserves its current behavior. `CodexExecExecutor` requires context because it needs a run directory and event sink.

## Web Service Flow

`GameReverseWebService.start_run(payload)` continues to validate known runner, availability, package name, max steps, mission, and safe actions.

For every accepted run, the service creates:

```text
<output_root>/<run_id>/
```

The service passes `ExecutorRunContext(run_id, run_dir, emit_event)` into `executor.start(...)`.

For `game_reverse`, the in-process runner can still return its own session directory. The pre-created run directory remains harmless and can be cleaned in a later maintenance pass if desired.

For `codex_exec`, the returned session directory is the context run directory.

The service still owns lifecycle events:

- `run_queued`
- `run_started`
- `run_completed`
- `run_failed`

The adapter owns runner-specific events:

- `runner_process_started`
- `runner_event`
- `runner_parse_error`
- `runner_stderr`
- `runner_timeout`
- `runner_process_failed`

## Codex Command

Build arguments as a list:

```python
[
    "codex",
    "exec",
    "--cd",
    repo_root,
    "--sandbox",
    "workspace-write",
    "--json",
    "--output-last-message",
    final_message_path,
    prompt,
]
```

Optional additions:

- `--profile <profile>` when `GAME_REVERSE_CODEX_PROFILE` is non-empty.
- `--model <model>` when `GAME_REVERSE_CODEX_MODEL` is non-empty.

Do not add:

- shell strings
- `--dangerously-bypass-approvals-and-sandbox`
- browser-provided command fragments
- browser-provided `--config` flags

`repo_root` remains validated with the existing containment check.

## Prompt Content

The prompt remains generated by the adapter. It should include:

- runner ID
- package name
- device URI
- mission type
- mission goal
- targets
- success criteria
- allowed actions
- max steps
- instruction to stay inside this repository
- instruction to use existing project tools and avoid unrelated code changes
- instruction to produce concise progress and a final summary

The prompt must not include:

- API keys
- authorization headers
- environment variable dumps
- browser-provided arbitrary shell commands
- local `.env` file contents

## Process Execution

`CodexExecExecutor.start(config, payload, context)` performs these steps:

1. Verify the runner is available.
2. Verify `context` is provided.
3. Create `context.run_dir`.
4. Build paths:
   - `codex_stdout.jsonl`
   - `codex_stderr.log`
   - `codex_last_message.txt`
   - `final_report.md`
5. Build the prompt and command.
6. Start `subprocess.Popen(args, cwd=repo_root, shell=False, stdout=PIPE, stderr=PIPE, text=True, encoding="utf-8", errors="replace")`.
7. Emit `runner_process_started` with redacted command metadata, not the full prompt.
8. Drain stderr on a helper thread and write it to `codex_stderr.log`.
9. Read stdout line by line:
   - write each line to `codex_stdout.jsonl`
   - parse each line through the existing Codex JSONL parser
   - emit resulting events through `context.emit_event`
10. Wait for process completion with the configured timeout.
11. On timeout, terminate then kill if needed, emit `runner_timeout`, and raise `ExecutorError`.
12. On non-zero exit, emit `runner_process_failed` and raise `ExecutorError`.
13. On success, write `final_report.md` from the last-message file plus links to captured logs.
14. Return `context.run_dir`.

## Log And Report Files

The Codex run directory contains:

```text
codex_stdout.jsonl
codex_stderr.log
codex_last_message.txt
final_report.md
```

`final_report.md` is generated by this project, not assumed to be written by Codex. It includes:

- run ID
- runner ID
- package name
- mission goal
- exit status
- last Codex message when available
- paths to stdout and stderr logs

This keeps the existing `/api/sessions/<id>/report` route useful without requiring Codex to know the project report file contract.

## Error Handling

Availability failures:

- If disabled, metadata reports unavailable.
- If enabled but the binary cannot be found, metadata reports unavailable with a description mentioning the missing command.
- Starting an unavailable runner is rejected before a background run is created.

Runtime failures:

- Missing context raises `ExecutorError("run context is required")`.
- Process spawn failure raises `ExecutorError("failed to start codex exec: ...")`.
- Timeout raises `ExecutorError("codex exec timed out")`.
- Non-zero exit raises `ExecutorError("codex exec exited with code N")`.

The Web service maps `ExecutorError` to existing failed run records when it happens inside the background thread.

## Redaction

Parsed JSON event `raw` fields continue through the existing recursive redaction helper.

Additional runtime event rules:

- Do not emit full prompt text.
- Do not emit environment variables.
- Do not emit stdout/stderr lines before parser redaction except parse-error line payloads.
- If stderr is surfaced as `runner_stderr`, truncate each event message to a short diagnostic string.
- Full stderr is still written to `codex_stderr.log` for local operator inspection.

## Testing

Add focused unit tests:

- Default registry keeps `codex_exec` unavailable.
- `GAME_REVERSE_ENABLE_CODEX_EXEC=1` plus found binary makes `codex_exec` available.
- Enable flag without binary leaves it unavailable.
- Command builder includes `--cd`, `--sandbox`, `--json`, and `--output-last-message`.
- Command builder omits empty profile/model.
- Command builder includes non-empty profile/model.
- `GameReverseExecutor.start(..., context=...)` remains backward compatible.
- Web service passes an `ExecutorRunContext` into selected adapters.
- Fake Codex process stdout lines become service run events.
- Fake Codex process writes stdout/stderr/last-message/report files.
- Fake timeout emits `runner_timeout` and fails the run.
- Fake non-zero exit emits `runner_process_failed` and fails the run.
- No test starts the real `codex` binary.

Run the focused suite:

```text
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service tests.test_game_reverse_web_server
```

Run the existing project-focused suite used by prior phases:

```text
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor tests.test_game_reverse_config tests.test_game_reverse_journal tests.test_game_reverse_llm_decider tests.test_game_reverse_mission tests.test_game_reverse_report_writer tests.test_game_reverse_run_loop
```

Run JavaScript syntax verification:

```text
node --check web/app.js
```

## Future Work

After this phase:

- Add a stop/cancel endpoint.
- Add UI controls for selecting enabled runners and showing CLI availability reasons.
- Add ClaudeCode real runner after verifying its current local CLI contract.
- Add optional SSE or WebSocket updates if polling becomes too coarse.
- Add operator-facing docs for environment variable setup and safe run defaults.
