# Executor Adapter Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a testable executor adapter layer behind the Web backend while keeping `game_reverse` as the only live runner and `codex_exec` / `claude_print` disabled.

**Architecture:** Create `game_reverse.executors` for runner metadata, adapter registry, prompt builders, command argument construction, repo path validation, event parsing, and redaction. Update `GameReverseWebService` to use the registry for health metadata and selected runner execution while preserving its existing run registry, background thread, session, and report behavior.

**Tech Stack:** Python standard library (`dataclasses`, `json`, `os`, `threading`), existing `game_reverse.web_service`, `unittest`.

---

## File Structure

- Create `game_reverse/executors.py`: adapter classes, registry, executor errors, command builders, prompt builders, event parsers, redaction.
- Create `tests/test_game_reverse_executors.py`: unit tests for registry metadata, command arguments, prompt building, repo path validation, event parsing, and redaction.
- Modify `game_reverse/web_service.py`: inject executor registry, get runner metadata from registry, route `start_run()` through selected adapter, map `ExecutorError` to `ValidationError`.
- Modify `tests/test_game_reverse_web_service.py`: assert registry-backed health, disabled runner validation, and existing `game_reverse` run behavior.
- Verify `tests/test_game_reverse_web_server.py`: no route change expected; existing tests should pass.
- Update `docs/superpowers/plans/2026-06-17-executor-adapter-layer.md`: mark completed steps during implementation.

## Task 1: Executor Registry And Metadata

**Files:**
- Create: `tests/test_game_reverse_executors.py`
- Create: `game_reverse/executors.py`

- [x] **Step 1: Write failing executor metadata tests**

Create `tests/test_game_reverse_executors.py` with:

```python
# -*- coding: utf-8 -*-
"""Tests for game explorer executor adapters."""

import os
import unittest

from game_reverse.executors import (
    ClaudePrintExecutor,
    CodexExecExecutor,
    ExecutorRegistry,
    GameReverseExecutor,
    create_default_registry,
    validate_repo_root,
)


class TestExecutorRegistry(unittest.TestCase):
    def test_default_registry_lists_all_runner_metadata(self):
        registry = create_default_registry(runner=lambda config: "session-dir")

        runners = registry.metadata()

        self.assertEqual([runner["id"] for runner in runners], ["game_reverse", "codex_exec", "claude_print"])
        self.assertTrue(runners[0]["available"])
        self.assertFalse(runners[1]["available"])
        self.assertFalse(runners[2]["available"])

    def test_registry_rejects_unknown_runner(self):
        registry = ExecutorRegistry([GameReverseExecutor(lambda config: "session-dir")])

        with self.assertRaisesRegex(KeyError, "missing"):
            registry.get("missing")

    def test_game_reverse_executor_delegates_to_runner(self):
        calls = []

        def fake_runner(config):
            calls.append(config)
            return "session-dir"

        executor = GameReverseExecutor(fake_runner)

        result = executor.start(config={"package_name": "com.example.game"}, payload={})

        self.assertEqual(result, "session-dir")
        self.assertEqual(calls, [{"package_name": "com.example.game"}])
```

- [x] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: fail with `ModuleNotFoundError: No module named 'game_reverse.executors'`.

- [x] **Step 3: Implement minimal registry and metadata**

Create `game_reverse/executors.py` with:

```python
# -*- coding: utf-8 -*-
"""Executor adapter boundary for game explorer runners."""

import os
from dataclasses import dataclass


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ExecutorError(ValueError):
    """Raised when executor adapter input is invalid."""


class ExecutorUnavailableError(ExecutorError):
    """Raised when a known executor is intentionally disabled."""


@dataclass
class GameReverseExecutor:
    runner: object
    id: str = "game_reverse"
    name: str = "game_reverse"
    available: bool = True
    description: str = "Run the local game_reverse loop with validated config."

    def metadata(self):
        return {
            "id": self.id,
            "name": self.name,
            "available": self.available,
            "description": self.description,
        }

    def start(self, config, payload):
        return self.runner(config)


@dataclass
class CodexExecExecutor:
    project_root: str = PROJECT_ROOT
    id: str = "codex_exec"
    name: str = "Codex CLI"
    available: bool = False
    description: str = "Planned executor adapter; not enabled in this phase."

    def metadata(self):
        return {
            "id": self.id,
            "name": self.name,
            "available": self.available,
            "description": self.description,
        }

    def start(self, config, payload):
        raise ExecutorUnavailableError("runner is not available")


@dataclass
class ClaudePrintExecutor:
    project_root: str = PROJECT_ROOT
    id: str = "claude_print"
    name: str = "ClaudeCode CLI"
    available: bool = False
    description: str = "Planned executor adapter; not enabled in this phase."

    def metadata(self):
        return {
            "id": self.id,
            "name": self.name,
            "available": self.available,
            "description": self.description,
        }

    def start(self, config, payload):
        raise ExecutorUnavailableError("runner is not available")


class ExecutorRegistry:
    def __init__(self, executors):
        self.executors = {executor.id: executor for executor in executors}

    def metadata(self):
        return [self.executors[runner_id].metadata() for runner_id in self.executors]

    def get(self, runner_id):
        if runner_id not in self.executors:
            raise KeyError(runner_id)
        return self.executors[runner_id]


def create_default_registry(runner):
    return ExecutorRegistry(
        [
            GameReverseExecutor(runner),
            CodexExecExecutor(),
            ClaudePrintExecutor(),
        ]
    )


def validate_repo_root(repo_root, project_root=PROJECT_ROOT):
    project_root = os.path.abspath(project_root)
    repo_root = os.path.abspath(repo_root)
    if os.path.commonpath([project_root, repo_root]) != project_root:
        raise ExecutorError("repo_root must stay inside project")
    return repo_root
```

- [x] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: pass.

## Task 2: Command Builders, Prompt Builders, And Repo Validation

**Files:**
- Modify: `tests/test_game_reverse_executors.py`
- Modify: `game_reverse/executors.py`

- [x] **Step 1: Add failing command and prompt tests**

Append to `tests/test_game_reverse_executors.py`:

```python
class TestExecutorCommandBuilders(unittest.TestCase):
    def payload(self):
        return {
            "package_name": "com.example.game",
            "allowed_actions": ["screenshot", "wait", "back"],
            "mission": {
                "type": "free_explore",
                "goal": "Explore tutorial",
                "targets": ["start button"],
                "success_criteria": ["write report"],
            },
            "api_key": "should-not-leak",
            "authorization": "Bearer should-not-leak",
        }

    def test_codex_builds_argument_list_without_shell_string(self):
        executor = CodexExecExecutor(project_root=os.getcwd())
        prompt = executor.build_prompt(self.payload(), config=None)

        args = executor.build_command(prompt, repo_root=os.getcwd())

        self.assertEqual(args[:5], ["codex", "exec", "--cd", os.path.abspath(os.getcwd()), "--json"])
        self.assertEqual(args[5], prompt)
        self.assertTrue(all(isinstance(part, str) for part in args))

    def test_claude_builds_argument_list_without_shell_string(self):
        executor = ClaudePrintExecutor(project_root=os.getcwd())
        prompt = executor.build_prompt(self.payload(), config=None)

        args = executor.build_command(prompt)

        self.assertEqual(args, ["claude", "-p", "--output-format", "stream-json", prompt])

    def test_prompt_contains_mission_context_but_not_secret_like_fields(self):
        prompt = CodexExecExecutor(project_root=os.getcwd()).build_prompt(self.payload(), config=None)

        self.assertIn("com.example.game", prompt)
        self.assertIn("Explore tutorial", prompt)
        self.assertIn("screenshot, wait, back", prompt)
        self.assertNotIn("should-not-leak", prompt)
        self.assertNotIn("api_key", prompt)
        self.assertNotIn("authorization", prompt)

    def test_validate_repo_root_rejects_parent_directory(self):
        project_root = os.path.join(os.getcwd(), "project")
        parent = os.path.dirname(project_root)

        with self.assertRaisesRegex(Exception, "repo_root"):
            validate_repo_root(parent, project_root=project_root)
```

- [x] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: fail because `build_prompt()` and `build_command()` do not exist.

- [x] **Step 3: Implement command and prompt builders**

Update `game_reverse/executors.py`:

```python
SECRET_PROMPT_KEYS = {"api_key", "authorization", "token", "secret", "password"}


def build_runner_prompt(payload, runner_id):
    mission = payload.get("mission") or {}
    allowed_actions = payload.get("allowed_actions") or []
    lines = [
        "Runner: %s" % runner_id,
        "Package: %s" % payload.get("package_name", ""),
        "Mission type: %s" % mission.get("type", "free_explore"),
        "Mission goal: %s" % mission.get("goal", ""),
        "Targets: %s" % ", ".join(mission.get("targets") or []),
        "Success criteria: %s" % ", ".join(mission.get("success_criteria") or []),
        "Allowed actions: %s" % ", ".join(allowed_actions),
        "Stay within this repository and produce structured progress events.",
    ]
    return "\n".join(lines)
```

Add methods to `CodexExecExecutor`:

```python
    def build_prompt(self, payload, config):
        return build_runner_prompt(payload, self.id)

    def build_command(self, prompt, repo_root=None):
        repo_root = validate_repo_root(repo_root or self.project_root, self.project_root)
        return ["codex", "exec", "--cd", repo_root, "--json", prompt]
```

Add methods to `ClaudePrintExecutor`:

```python
    def build_prompt(self, payload, config):
        return build_runner_prompt(payload, self.id)

    def build_command(self, prompt, repo_root=None):
        repo_root = validate_repo_root(repo_root or self.project_root, self.project_root)
        return ["claude", "-p", "--output-format", "stream-json", prompt]
```

- [x] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: pass.

## Task 3: Event Parsers And Redaction

**Files:**
- Modify: `tests/test_game_reverse_executors.py`
- Modify: `game_reverse/executors.py`

- [x] **Step 1: Add failing parser tests**

Append to `tests/test_game_reverse_executors.py`:

```python
class TestExecutorEventParsers(unittest.TestCase):
    def test_codex_parser_maps_jsonl_events(self):
        lines = [
            '{"type": "started", "message": "run started"}',
            "",
            '{"type": "assistant_message", "message": "observed screen"}',
        ]

        events = CodexExecExecutor().parse_events(lines)

        self.assertEqual([event["type"] for event in events], ["runner_event", "runner_event"])
        self.assertEqual(events[0]["source"], "codex_exec")
        self.assertEqual(events[0]["message"], "run started")

    def test_claude_parser_maps_stream_json_events(self):
        lines = [
            '{"type": "system", "subtype": "init"}',
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "ready"}]}}',
        ]

        events = ClaudePrintExecutor().parse_events(lines)

        self.assertEqual([event["type"] for event in events], ["runner_event", "runner_event"])
        self.assertEqual(events[0]["source"], "claude_print")
        self.assertIn("init", events[0]["message"])
        self.assertEqual(events[1]["message"], "ready")

    def test_invalid_json_line_becomes_parse_error(self):
        events = CodexExecExecutor().parse_events(["not json"])

        self.assertEqual(events[0]["type"], "runner_parse_error")
        self.assertEqual(events[0]["source"], "codex_exec")
        self.assertEqual(events[0]["raw"], {"line": "not json"})

    def test_secret_like_raw_keys_are_redacted(self):
        events = CodexExecExecutor().parse_events([
            '{"message": "done", "api_key": "secret-value", "nested": {"password": "pw"}}'
        ])

        self.assertEqual(events[0]["raw"]["api_key"], "[redacted]")
        self.assertEqual(events[0]["raw"]["nested"]["password"], "[redacted]")
```

- [x] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: fail because `parse_events()` does not exist.

- [x] **Step 3: Implement parser and redaction helpers**

Update `game_reverse/executors.py`:

```python
import json
```

Add helpers:

```python
REDACTED_VALUE = "[redacted]"
SECRET_KEY_PARTS = ("key", "token", "secret", "password", "authorization")


def parse_jsonl_events(lines, source, message_extractor):
    events = []
    for line in lines:
        if not line or not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            events.append(
                {
                    "type": "runner_parse_error",
                    "source": source,
                    "message": "invalid json",
                    "raw": {"line": line},
                }
            )
            continue
        events.append(
            {
                "type": "runner_event",
                "source": source,
                "message": message_extractor(raw),
                "raw": redact_secrets(raw),
            }
        )
    return events


def redact_secrets(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(part in key.lower() for part in SECRET_KEY_PARTS):
                redacted[key] = REDACTED_VALUE
            else:
                redacted[key] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def codex_message(raw):
    return str(raw.get("message") or raw.get("type") or "event")


def claude_message(raw):
    message = raw.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            texts = [item.get("text", "") for item in content if isinstance(item, dict)]
            text = " ".join(text for text in texts if text)
            if text:
                return text
    subtype = raw.get("subtype")
    if subtype:
        return "%s:%s" % (raw.get("type", "event"), subtype)
    return str(raw.get("message") or raw.get("type") or "event")
```

Add methods to `CodexExecExecutor`:

```python
    def parse_events(self, lines):
        return parse_jsonl_events(lines, self.id, codex_message)
```

Add methods to `ClaudePrintExecutor`:

```python
    def parse_events(self, lines):
        return parse_jsonl_events(lines, self.id, claude_message)
```

- [x] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: pass.

## Task 4: Web Service Registry Integration

**Files:**
- Modify: `tests/test_game_reverse_web_service.py`
- Modify: `game_reverse/web_service.py`

- [x] **Step 1: Add failing service integration tests**

Modify `tests/test_game_reverse_web_service.py`.

Add import:

```python
from game_reverse.executors import create_default_registry
```

Add tests:

```python
    def test_health_uses_executor_registry_metadata(self):
        service = self.make_service()

        health = service.health()

        runners = {runner["id"]: runner for runner in health["runners"]}
        self.assertTrue(runners["game_reverse"]["available"])
        self.assertFalse(runners["codex_exec"]["available"])
        self.assertFalse(runners["claude_print"]["available"])

    def test_rejects_disabled_codex_runner_as_unavailable(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["runner"] = "codex_exec"

        with self.assertRaisesRegex(ValidationError, "not available"):
            service.start_run(payload)

    def test_rejects_disabled_claude_runner_as_unavailable(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["runner"] = "claude_print"

        with self.assertRaisesRegex(ValidationError, "not available"):
            service.start_run(payload)
```

Update the existing `test_rejects_unknown_runner` to use an actually unknown runner:

```python
        payload["runner"] = "unknown_runner"
```

- [x] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service
```

Expected: fail because the current service rejects `codex_exec` as a phase error instead of registry unavailable, and health is still hard-coded.

- [x] **Step 3: Integrate registry in `web_service`**

Update imports in `game_reverse/web_service.py`:

```python
from game_reverse.executors import ExecutorError, create_default_registry
```

Update `__init__`:

```python
    def __init__(self, output_root=None, runner=None, executors=None):
        self.output_root = output_root or "game_reverse/outputs/sessions"
        self.runner = runner or run_loop
        self.executors = executors or create_default_registry(self.runner)
        self.runs = {}
```

Update `health()`:

```python
    def health(self):
        return {
            "status": "ok",
            "static_only": False,
            "runners": self.executors.metadata(),
        }
```

Update `start_run()` before creating the run record:

```python
        if not isinstance(payload, dict):
            raise ValidationError("payload must be an object")

        runner_id = payload.get("runner", "game_reverse")
        try:
            executor = self.executors.get(runner_id)
        except KeyError:
            raise ValidationError("runner must be a known runner")

        config = self._config_from_payload(payload)
```

Set the record runner dynamically:

```python
            "runner": runner_id,
```

Start background thread with executor:

```python
        thread = threading.Thread(target=self._run_background, args=(run_id, executor, config, payload))
```

Update `_config_from_payload()` to remove the hard-coded runner restriction:

```python
        runner = payload.get("runner", "game_reverse")
        if not isinstance(runner, str) or not runner:
            raise ValidationError("runner must be a non-empty string")
```

Update `_run_background()` signature and execution:

```python
    def _run_background(self, run_id, executor, config, payload):
        ...
            session_dir = executor.start(config, payload)
        except ExecutorError as exc:
            with self.lock:
                record = self.runs[run_id]
                record.update(
                    {
                        "status": "failed",
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                    }
                )
                self._append_event_locked(
                    run_id,
                    "run_failed",
                    error_type=exc.__class__.__name__,
                    error=str(exc),
                )
            return
        except Exception as exc:
            ...
```

Important: Disabled runners will create a run and fail in the background if the service starts them this way. To keep the validation behavior expected by the tests, reject disabled runners synchronously before creating a run:

```python
        if not executor.available:
            raise ValidationError("runner is not available")
```

- [x] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service tests.test_game_reverse_executors
```

Expected: pass.

## Task 5: Full Verification And Browser Smoke

**Files:**
- Verify only unless failures require fixes.

- [x] **Step 1: Run focused test suite**

Run:

```bash
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor tests.test_game_reverse_config tests.test_game_reverse_journal tests.test_game_reverse_llm_decider tests.test_game_reverse_mission tests.test_game_reverse_report_writer tests.test_game_reverse_run_loop
```

Expected: all tests pass.

- [x] **Step 2: Run JS syntax check**

Run:

```bash
node --check web/app.js
```

Expected: exit code 0.

- [x] **Step 3: Start backend smoke server**

Run:

```bash
python -m game_reverse.web_server --host 127.0.0.1 --port 8768
```

Open:

```text
http://127.0.0.1:8768/web/index.html
```

Verify:

- backend online badge appears
- start button is enabled
- runner list still shows `game_reverse`, `codex_exec`, and `claude_print`
- `codex_exec` and `claude_print` are still presented as planned/unavailable
- do not click start unless the user explicitly asks for a real run

- [x] **Step 4: Stop smoke server**

Stop the backend process started in Step 3.

## Task 6: Final Checks And Commit

**Files:**
- Add: `game_reverse/executors.py`
- Add: `tests/test_game_reverse_executors.py`
- Modify: `game_reverse/web_service.py`
- Modify: `tests/test_game_reverse_web_service.py`
- Modify: `docs/superpowers/plans/2026-06-17-executor-adapter-layer.md`

- [x] **Step 1: Final checks**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended files changed.

- [ ] **Step 2: Commit**

Run:

```bash
git add game_reverse/executors.py tests/test_game_reverse_executors.py game_reverse/web_service.py tests/test_game_reverse_web_service.py docs/superpowers/plans/2026-06-17-executor-adapter-layer.md
git commit -m "Add executor adapter layer"
```

Expected: commit succeeds.
