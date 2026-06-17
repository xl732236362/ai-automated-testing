# Codex Exec Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `codex_exec` an opt-in real executor that launches local `codex exec`, emits JSONL progress into Web run events, and writes Codex logs/reports into the existing session output area.

**Architecture:** Extend the executor adapter contract with an `ExecutorRunContext` owned by `GameReverseWebService`. Keep process execution inside `CodexExecExecutor`, use `subprocess.Popen(shell=False)`, stream stdout/stderr through redacted events and local log files, and keep the runner unavailable unless environment configuration explicitly enables it and the CLI binary is found.

**Tech Stack:** Python standard library (`dataclasses`, `os`, `shutil`, `subprocess`, `threading`, `unittest`, `tempfile`), existing `game_reverse.executors`, existing `game_reverse.web_service`, existing static Web polling API.

---

## File Structure

- Modify `game_reverse/executors.py`: add run context, environment-backed Codex availability, Codex process execution, stdout/stderr draining, timeout handling, final report writing.
- Modify `game_reverse/web_service.py`: create a per-run directory, pass `ExecutorRunContext` to adapters, expose adapter-emitted events through existing polling.
- Modify `tests/test_game_reverse_executors.py`: add availability, command, process success, timeout, non-zero exit, and report/log tests using fake processes.
- Modify `tests/test_game_reverse_web_service.py`: add context-passing and adapter event integration tests.
- Verify `tests/test_game_reverse_web_server.py`: no route changes expected.
- Verify `web/app.js`: no JavaScript changes expected in this phase.

## Task 1: Adapter Context Contract

**Files:**
- Modify: `tests/test_game_reverse_executors.py`
- Modify: `tests/test_game_reverse_web_service.py`
- Modify: `game_reverse/executors.py`
- Modify: `game_reverse/web_service.py`

- [x] **Step 1: Write failing executor context tests**

In `tests/test_game_reverse_executors.py`, update `test_game_reverse_executor_delegates_to_runner` so it proves the new optional context argument does not break the local runner:

```python
    def test_game_reverse_executor_delegates_to_runner_with_optional_context(self):
        calls = []

        def fake_runner(config):
            calls.append(config)
            return "session-dir"

        executor = GameReverseExecutor(fake_runner)
        context = object()

        result = executor.start(
            config={"package_name": "com.example.game"},
            payload={},
            context=context,
        )

        self.assertEqual(result, "session-dir")
        self.assertEqual(calls, [{"package_name": "com.example.game"}])
```

Remove the old `test_game_reverse_executor_delegates_to_runner` or rename it to the new test above.

- [x] **Step 2: Write failing Web service context test**

In `tests/test_game_reverse_web_service.py`, add imports:

```python
from game_reverse.executors import ExecutorRegistry, create_default_registry
```

Add this fake adapter above `TestGameReverseWebService`:

```python
class RecordingExecutor:
    id = "recording"
    name = "Recording"
    available = True
    description = "Records the context passed by the Web service."

    def __init__(self):
        self.contexts = []

    def metadata(self):
        return {
            "id": self.id,
            "name": self.name,
            "available": self.available,
            "description": self.description,
        }

    def start(self, config, payload, context=None):
        self.contexts.append(context)
        os.makedirs(context.run_dir, exist_ok=True)
        context.emit_event("runner_event", source=self.id, message="adapter event")
        report_path = os.path.join(context.run_dir, "final_report.md")
        with open(report_path, "w", encoding="utf-8") as report:
            report.write("# Recording Report\n")
        return context.run_dir
```

Add this test:

```python
    def test_passes_run_context_to_executor_and_records_adapter_events(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        executor = RecordingExecutor()
        registry = ExecutorRegistry([executor])
        service = GameReverseWebService(
            output_root=self.tmpdir.name,
            runner=FakeRunner(),
            executors=registry,
        )
        payload = self.valid_payload()
        payload["runner"] = "recording"

        result = service.start_run(payload)
        completed = self.wait_for_status(service, result["id"], "completed")

        self.assertEqual(len(executor.contexts), 1)
        context = executor.contexts[0]
        self.assertEqual(context.run_id, result["id"])
        self.assertTrue(context.run_dir.startswith(self.tmpdir.name))
        self.assertEqual(completed["session_dir"], context.run_dir)
        events = service.run_events(result["id"])
        self.assertTrue(any(event["type"] == "runner_event" for event in events))
        report = service.session_report(result["id"])
        self.assertIn("# Recording Report", report["final_report"])
```

- [x] **Step 3: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service
```

Expected: fail because `GameReverseExecutor.start()` does not accept `context`, `ExecutorRunContext` does not exist, and Web service still calls `executor.start(config, payload)`.

- [x] **Step 4: Add `ExecutorRunContext` and update adapter signatures**

In `game_reverse/executors.py`, add the context dataclass after the executor error classes:

```python
@dataclass
class ExecutorRunContext:
    run_id: str
    run_dir: str
    emit_event: object
```

Update the local executor signature:

```python
    def start(self, config, payload, context=None):
        return self.runner(config)
```

Update disabled external executor signatures:

```python
    def start(self, config, payload, context=None):
        raise ExecutorUnavailableError("runner is not available")
```

- [x] **Step 5: Pass context from the Web service**

In `game_reverse/web_service.py`, update imports:

```python
from game_reverse.executors import ExecutorError, ExecutorRunContext, create_default_registry
```

In `start_run()`, keep the existing record shape. No field is added to the initial API response.

Update `_run_background()`:

```python
    def _run_background(self, run_id, executor, config, payload):
        with self.lock:
            record = self.runs[run_id]
            record["status"] = "running"
            self._append_event_locked(run_id, "run_started")

        run_dir = os.path.join(config.output_root, run_id)

        def emit_event(event_type, **extra):
            with self.lock:
                self._append_event_locked(run_id, event_type, **extra)

        context = ExecutorRunContext(
            run_id=run_id,
            run_dir=run_dir,
            emit_event=emit_event,
        )

        try:
            session_dir = executor.start(config, payload, context=context)
```

Leave the existing `except ExecutorError`, generic `except Exception`, and success update blocks in place.

- [x] **Step 6: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service
```

Expected: all tests pass.

- [x] **Step 7: Commit Task 1**

Run:

```bash
git add game_reverse/executors.py game_reverse/web_service.py tests/test_game_reverse_executors.py tests/test_game_reverse_web_service.py
git commit -m "Add executor run context"
```

Expected: commit succeeds.

## Task 2: Codex Availability From Environment

**Files:**
- Modify: `tests/test_game_reverse_executors.py`
- Modify: `game_reverse/executors.py`

- [x] **Step 1: Write failing availability tests**

In `tests/test_game_reverse_executors.py`, update `test_default_registry_lists_all_runner_metadata` so it is independent of the operator's environment:

```python
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={},
        )
```

Then add these tests to `TestExecutorRegistry`:

```python
    def test_codex_exec_is_available_when_enabled_and_binary_exists(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={"GAME_REVERSE_ENABLE_CODEX_EXEC": "1"},
            codex_which=lambda command: "C:/tools/codex.cmd",
        )

        runners = {runner["id"]: runner for runner in registry.metadata()}

        self.assertTrue(runners["codex_exec"]["available"])
        self.assertIn("Codex", runners["codex_exec"]["description"])

    def test_codex_exec_is_unavailable_when_enabled_but_binary_missing(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={"GAME_REVERSE_ENABLE_CODEX_EXEC": "1"},
            codex_which=lambda command: None,
        )

        runners = {runner["id"]: runner for runner in registry.metadata()}

        self.assertFalse(runners["codex_exec"]["available"])
        self.assertIn("not found", runners["codex_exec"]["description"])

    def test_codex_exec_reads_environment_options(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={
                "GAME_REVERSE_ENABLE_CODEX_EXEC": "1",
                "GAME_REVERSE_CODEX_COMMAND": "codex-custom",
                "GAME_REVERSE_CODEX_TIMEOUT_SECONDS": "123",
                "GAME_REVERSE_CODEX_SANDBOX": "read-only",
                "GAME_REVERSE_CODEX_PROFILE": "local",
                "GAME_REVERSE_CODEX_MODEL": "gpt-5.1-codex",
            },
            codex_which=lambda command: "C:/tools/%s.cmd" % command,
        )

        executor = registry.get("codex_exec")

        self.assertTrue(executor.available)
        self.assertEqual(executor.command, "codex-custom")
        self.assertEqual(executor.timeout_seconds, 123)
        self.assertEqual(executor.sandbox, "read-only")
        self.assertEqual(executor.profile, "local")
        self.assertEqual(executor.model, "gpt-5.1-codex")
```

- [x] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: fail because `create_default_registry()` does not accept `environ` or `codex_which`, and `CodexExecExecutor` has static availability.

- [x] **Step 3: Implement environment-backed availability**

In `game_reverse/executors.py`, update imports:

```python
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
```

Replace `CodexExecExecutor` with:

```python
@dataclass
class CodexExecExecutor:
    project_root: str = PROJECT_ROOT
    enabled: bool = False
    command: str = "codex"
    timeout_seconds: int = 900
    sandbox: str = "workspace-write"
    profile: str = ""
    model: str = ""
    popen_factory: object = field(default=subprocess.Popen, repr=False)
    which: object = field(default=shutil.which, repr=False)
    id: str = "codex_exec"
    name: str = "Codex CLI"
    description: str = "Codex CLI runner is disabled. Set GAME_REVERSE_ENABLE_CODEX_EXEC=1 to enable it."

    def __post_init__(self):
        self.command_path = self.which(self.command) if self.command else None
        self.available = bool(self.enabled and self.command_path)
        if self.available:
            self.description = "Run local Codex CLI non-interactively with codex exec."
        elif self.enabled:
            self.description = "Codex CLI command not found: %s" % self.command

    def metadata(self):
        return {
            "id": self.id,
            "name": self.name,
            "available": self.available,
            "description": self.description,
        }
```

Add helpers near `create_default_registry()`:

```python
def env_flag_enabled(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed
```

Replace `create_default_registry()` with:

```python
def create_default_registry(runner, environ=None, codex_which=None, codex_popen_factory=None):
    if environ is None:
        environ = os.environ
    if codex_which is None:
        codex_which = shutil.which
    if codex_popen_factory is None:
        codex_popen_factory = subprocess.Popen
    return ExecutorRegistry(
        [
            GameReverseExecutor(runner),
            CodexExecExecutor(
                enabled=env_flag_enabled(environ.get("GAME_REVERSE_ENABLE_CODEX_EXEC")),
                command=environ.get("GAME_REVERSE_CODEX_COMMAND", "codex") or "codex",
                timeout_seconds=parse_positive_int(
                    environ.get("GAME_REVERSE_CODEX_TIMEOUT_SECONDS"),
                    900,
                ),
                sandbox=environ.get("GAME_REVERSE_CODEX_SANDBOX", "workspace-write")
                or "workspace-write",
                profile=environ.get("GAME_REVERSE_CODEX_PROFILE", "") or "",
                model=environ.get("GAME_REVERSE_CODEX_MODEL", "") or "",
                which=codex_which,
                popen_factory=codex_popen_factory,
            ),
            ClaudePrintExecutor(),
        ]
    )
```

Keep `CodexExecExecutor.start()` temporarily raising `ExecutorUnavailableError("runner is not available")`; Task 4 replaces it.

In `tests/test_game_reverse_web_service.py`, update `make_service()` to keep default Web-service tests deterministic even if the operator has enabled Codex in the shell:

```python
    def make_service(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.runner = FakeRunner()
        return GameReverseWebService(
            output_root=self.tmpdir.name,
            runner=self.runner,
            executors=create_default_registry(self.runner, environ={}),
        )
```

- [x] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service
```

Expected: all tests pass.

- [x] **Step 5: Commit Task 2**

Run:

```bash
git add game_reverse/executors.py tests/test_game_reverse_executors.py
git commit -m "Enable Codex runner availability config"
```

Expected: commit succeeds.

## Task 3: Codex Prompt And Command Shape

**Files:**
- Modify: `tests/test_game_reverse_executors.py`
- Modify: `game_reverse/executors.py`

- [x] **Step 1: Update command and prompt tests**

In `tests/test_game_reverse_executors.py`, update `test_codex_builds_argument_list_without_shell_string`:

```python
    def test_codex_builds_argument_list_without_shell_string(self):
        executor = CodexExecExecutor(
            project_root=os.getcwd(),
            enabled=True,
            which=lambda command: command,
        )
        prompt = executor.build_prompt(self.payload(), config=None)
        final_message_path = os.path.join(os.getcwd(), "last-message.txt")

        args = executor.build_command(
            prompt,
            repo_root=os.getcwd(),
            final_message_path=final_message_path,
        )

        self.assertEqual(args[:7], [
            "codex",
            "exec",
            "--cd",
            os.path.abspath(os.getcwd()),
            "--sandbox",
            "workspace-write",
            "--json",
        ])
        self.assertIn("--output-last-message", args)
        self.assertEqual(args[args.index("--output-last-message") + 1], final_message_path)
        self.assertEqual(args[-1], prompt)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", args)
        self.assertTrue(all(isinstance(part, str) for part in args))
```

Add optional profile/model test:

```python
    def test_codex_command_includes_profile_and_model_when_configured(self):
        executor = CodexExecExecutor(
            project_root=os.getcwd(),
            enabled=True,
            profile="local",
            model="gpt-5.1-codex",
            which=lambda command: command,
        )
        prompt = executor.build_prompt(self.payload(), config=None)
        final_message_path = os.path.join(os.getcwd(), "last-message.txt")

        args = executor.build_command(
            prompt,
            repo_root=os.getcwd(),
            final_message_path=final_message_path,
        )

        self.assertEqual(args[args.index("--profile") + 1], "local")
        self.assertEqual(args[args.index("--model") + 1], "gpt-5.1-codex")
```

Update `test_prompt_contains_mission_context_but_not_secret_like_fields` so it checks the new fields:

```python
    def test_prompt_contains_runtime_context_but_not_secret_like_fields(self):
        prompt = CodexExecExecutor(project_root=os.getcwd()).build_prompt(
            self.payload(),
            config=None,
        )

        self.assertIn("com.example.game", prompt)
        self.assertIn("Explore tutorial", prompt)
        self.assertIn("screenshot, wait, back", prompt)
        self.assertIn("Stay within this repository", prompt)
        self.assertNotIn("should-not-leak", prompt)
        self.assertNotIn("api_key", prompt)
        self.assertNotIn("authorization", prompt)
```

- [x] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: fail because `build_command()` does not include sandbox or last-message output.

- [x] **Step 3: Implement Codex command shape**

In `CodexExecExecutor.build_command()`, replace the existing method with:

```python
    def build_command(self, prompt, repo_root=None, final_message_path=None):
        repo_root = validate_repo_root(repo_root or self.project_root, self.project_root)
        final_message_path = final_message_path or os.path.join(
            repo_root,
            "codex_last_message.txt",
        )
        args = [
            self.command,
            "exec",
            "--cd",
            repo_root,
            "--sandbox",
            self.sandbox,
            "--json",
            "--output-last-message",
            final_message_path,
        ]
        if self.profile:
            args.extend(["--profile", self.profile])
        if self.model:
            args.extend(["--model", self.model])
        args.append(prompt)
        return args
```

Update `CodexExecExecutor.build_prompt()`:

```python
    def build_prompt(self, payload, config):
        return build_runner_prompt(payload, self.id, config=config)
```

Replace `build_runner_prompt()` with:

```python
def build_runner_prompt(payload, runner_id, config=None):
    mission = payload.get("mission") or {}
    allowed_actions = payload.get("allowed_actions") or []
    device_uri = payload.get("device_uri", "")
    max_steps = payload.get("max_steps", "")
    if config is not None:
        mission = getattr(config, "mission", None) or mission
        allowed_actions = getattr(config, "allowed_actions", allowed_actions)
        device_uri = getattr(config, "device_uri", device_uri)
        max_steps = getattr(config, "max_steps", max_steps)

    mission_type = getattr(mission, "type", None)
    mission_goal = getattr(mission, "goal", None)
    mission_targets = getattr(mission, "targets", None)
    success_criteria = getattr(mission, "success_criteria", None)
    if isinstance(mission, dict):
        mission_type = mission_type or mission.get("type", "free_explore")
        mission_goal = mission_goal or mission.get("goal", "")
        mission_targets = mission_targets or mission.get("targets", [])
        success_criteria = success_criteria or mission.get("success_criteria", [])
    mission_type = mission_type or "free_explore"
    mission_goal = mission_goal or ""
    mission_targets = mission_targets or []
    success_criteria = success_criteria or []

    lines = [
        "Runner: %s" % runner_id,
        "Package: %s" % payload.get("package_name", ""),
        "Device URI: %s" % device_uri,
        "Mission type: %s" % mission_type,
        "Mission goal: %s" % mission_goal,
        "Targets: %s" % ", ".join(mission_targets or []),
        "Success criteria: %s" % ", ".join(success_criteria or []),
        "Allowed actions: %s" % ", ".join(allowed_actions or []),
        "Max steps: %s" % max_steps,
        "Stay within this repository.",
        "Use existing project tools and avoid unrelated code changes.",
        "Produce concise progress events and a final summary.",
    ]
    return "\n".join(lines)
```

Update `ClaudePrintExecutor.build_prompt()`:

```python
    def build_prompt(self, payload, config):
        return build_runner_prompt(payload, self.id, config=config)
```

- [x] **Step 4: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service
```

Expected: all tests pass.

- [x] **Step 5: Commit Task 3**

Run:

```bash
git add game_reverse/executors.py tests/test_game_reverse_executors.py
git commit -m "Define Codex exec command shape"
```

Expected: commit succeeds.

## Task 4: Codex Process Success Path

**Files:**
- Modify: `tests/test_game_reverse_executors.py`
- Modify: `game_reverse/executors.py`

- [x] **Step 1: Add fake process helpers**

In `tests/test_game_reverse_executors.py`, add this helper near the top of the file after imports:

```python
class FakeProcess:
    def __init__(self, stdout_lines=None, stderr_lines=None, returncode=0):
        self.stdout = stdout_lines or []
        self.stderr = stderr_lines or []
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True
```

Add a context helper:

```python
def make_context(run_id, run_dir, events):
    from game_reverse.executors import ExecutorRunContext

    def emit_event(event_type, **extra):
        event = {"type": event_type}
        event.update(extra)
        events.append(event)

    return ExecutorRunContext(run_id=run_id, run_dir=run_dir, emit_event=emit_event)
```

- [x] **Step 2: Write failing Codex success test**

Add this test class:

```python
class TestCodexExecProcess(unittest.TestCase):
    def payload(self):
        return {
            "package_name": "com.example.game",
            "device_uri": "Android:///emulator-5554",
            "allowed_actions": ["screenshot", "wait", "back"],
            "max_steps": 2,
            "mission": {
                "type": "free_explore",
                "goal": "Explore tutorial",
                "targets": ["start button"],
                "success_criteria": ["write report"],
            },
        }

    def test_codex_start_streams_events_and_writes_logs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            calls = []

            def fake_popen(args, **kwargs):
                calls.append((args, kwargs))
                final_path = args[args.index("--output-last-message") + 1]
                with open(final_path, "w", encoding="utf-8") as last_message:
                    last_message.write("Final Codex summary")
                return FakeProcess(
                    stdout_lines=[
                        '{"type": "started", "message": "run started"}\n',
                        '{"type": "assistant_message", "message": "observed screen"}\n',
                    ],
                    stderr_lines=["diagnostic line\n"],
                    returncode=0,
                )

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                popen_factory=fake_popen,
                which=lambda command: command,
            )
            context = make_context("run-001", os.path.join(tmpdir, "run-001"), events)

            session_dir = executor.start(config=None, payload=self.payload(), context=context)

            self.assertEqual(session_dir, context.run_dir)
            self.assertEqual(calls[0][1]["cwd"], os.path.abspath(os.getcwd()))
            self.assertFalse(calls[0][1]["shell"])
            self.assertTrue(os.path.exists(os.path.join(session_dir, "codex_stdout.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "codex_stderr.log")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "codex_last_message.txt")))
            report = open(os.path.join(session_dir, "final_report.md"), encoding="utf-8").read()
            self.assertIn("Final Codex summary", report)
            self.assertTrue(any(event["type"] == "runner_process_started" for event in events))
            self.assertTrue(any(event.get("message") == "run started" for event in events))
            self.assertTrue(any(event.get("message") == "observed screen" for event in events))
            self.assertTrue(any(event["type"] == "runner_stderr" for event in events))
```

Add imports at the top:

```python
import tempfile
```

- [x] **Step 3: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: fail because `CodexExecExecutor.start()` still raises `ExecutorUnavailableError`.

- [x] **Step 4: Implement Codex process success path**

In `game_reverse/executors.py`, add helper constants near the existing constants:

```python
CODEX_STDOUT_FILENAME = "codex_stdout.jsonl"
CODEX_STDERR_FILENAME = "codex_stderr.log"
CODEX_LAST_MESSAGE_FILENAME = "codex_last_message.txt"
FINAL_REPORT_FILENAME = "final_report.md"
```

Replace `CodexExecExecutor.start()` with:

```python
    def start(self, config, payload, context=None):
        if not self.available:
            raise ExecutorUnavailableError("runner is not available")
        if context is None:
            raise ExecutorError("run context is required")

        os.makedirs(context.run_dir, exist_ok=True)
        repo_root = validate_repo_root(self.project_root, self.project_root)
        stdout_path = os.path.join(context.run_dir, CODEX_STDOUT_FILENAME)
        stderr_path = os.path.join(context.run_dir, CODEX_STDERR_FILENAME)
        final_message_path = os.path.join(context.run_dir, CODEX_LAST_MESSAGE_FILENAME)
        report_path = os.path.join(context.run_dir, FINAL_REPORT_FILENAME)

        prompt = self.build_prompt(payload, config)
        args = self.build_command(
            prompt,
            repo_root=repo_root,
            final_message_path=final_message_path,
        )

        try:
            process = self.popen_factory(
                args,
                cwd=repo_root,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise ExecutorError("failed to start codex exec: %s" % exc)

        context.emit_event(
            "runner_process_started",
            source=self.id,
            command=self.command_for_event(args),
            cwd=repo_root,
        )

        stdout_thread = threading.Thread(
            target=self._drain_stdout,
            args=(process.stdout, stdout_path, context),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(process.stderr, stderr_path, context),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        return_code = process.wait(timeout=self.timeout_seconds)
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        if return_code != 0:
            context.emit_event(
                "runner_process_failed",
                source=self.id,
                exit_code=return_code,
            )
            raise ExecutorError("codex exec exited with code %s" % return_code)

        self._write_final_report(
            report_path=report_path,
            context=context,
            config=config,
            payload=payload,
            final_message_path=final_message_path,
            exit_code=return_code,
        )
        return context.run_dir
```

Add methods inside `CodexExecExecutor`:

```python
    def command_for_event(self, args):
        if not args:
            return []
        return list(args[:-1]) + ["[prompt]"]

    def _drain_stdout(self, stream, stdout_path, context):
        with open(stdout_path, "w", encoding="utf-8") as stdout_file:
            for line in stream or []:
                stdout_file.write(line)
                stdout_file.flush()
                for event in self.parse_events([line]):
                    self._emit_parsed_event(context, event)

    def _drain_stderr(self, stream, stderr_path, context):
        with open(stderr_path, "w", encoding="utf-8") as stderr_file:
            for line in stream or []:
                stderr_file.write(line)
                stderr_file.flush()
                message = line.strip()
                if message:
                    context.emit_event(
                        "runner_stderr",
                        source=self.id,
                        message=message[:300],
                    )

    def _emit_parsed_event(self, context, event):
        event_type = event.get("type", "runner_event")
        extra = dict(event)
        extra.pop("type", None)
        context.emit_event(event_type, **extra)

    def _write_final_report(
        self,
        report_path,
        context,
        config,
        payload,
        final_message_path,
        exit_code,
    ):
        final_message = ""
        if os.path.exists(final_message_path):
            with open(final_message_path, "r", encoding="utf-8") as message_file:
                final_message = message_file.read().strip()

        mission = payload.get("mission") or {}
        if config is not None:
            mission = getattr(config, "mission", None) or mission
        mission_goal = getattr(mission, "goal", None)
        if mission_goal is None and isinstance(mission, dict):
            mission_goal = mission.get("goal", "")
        mission_goal = mission_goal or ""

        lines = [
            "# Codex Exec Run",
            "",
            "- Run ID: %s" % context.run_id,
            "- Runner: %s" % self.id,
            "- Package: %s" % payload.get("package_name", ""),
            "- Mission goal: %s" % mission_goal,
            "- Exit code: %s" % exit_code,
            "",
            "## Final Message",
            "",
            final_message or "(no final message captured)",
            "",
            "## Logs",
            "",
            "- stdout: %s" % CODEX_STDOUT_FILENAME,
            "- stderr: %s" % CODEX_STDERR_FILENAME,
        ]
        with open(report_path, "w", encoding="utf-8") as report:
            report.write("\n".join(lines) + "\n")
```

- [x] **Step 5: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: all tests pass.

- [x] **Step 6: Commit Task 4**

Run:

```bash
git add game_reverse/executors.py tests/test_game_reverse_executors.py
git commit -m "Run Codex exec process"
```

Expected: commit succeeds.

## Task 5: Codex Runtime Failure Handling

**Files:**
- Modify: `tests/test_game_reverse_executors.py`
- Modify: `game_reverse/executors.py`

- [x] **Step 1: Add timeout fake process**

In `tests/test_game_reverse_executors.py`, add:

```python
class TimeoutFakeProcess(FakeProcess):
    def __init__(self):
        super().__init__(stdout_lines=[], stderr_lines=[], returncode=None)
        self.wait_calls = 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise subprocess.TimeoutExpired(cmd="codex", timeout=timeout)
        return -9
```

Add import:

```python
import subprocess
```

- [x] **Step 2: Write failing failure tests**

Add tests to `TestCodexExecProcess`:

```python
    def test_codex_timeout_terminates_process_and_emits_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            process = TimeoutFakeProcess()

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                timeout_seconds=1,
                popen_factory=lambda args, **kwargs: process,
                which=lambda command: command,
            )
            context = make_context("run-timeout", os.path.join(tmpdir, "run-timeout"), events)

            with self.assertRaisesRegex(Exception, "timed out"):
                executor.start(config=None, payload=self.payload(), context=context)

            self.assertTrue(process.terminated)
            self.assertTrue(any(event["type"] == "runner_timeout" for event in events))

    def test_codex_nonzero_exit_emits_failed_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                popen_factory=lambda args, **kwargs: FakeProcess(returncode=7),
                which=lambda command: command,
            )
            context = make_context("run-failed", os.path.join(tmpdir, "run-failed"), events)

            with self.assertRaisesRegex(Exception, "exited with code 7"):
                executor.start(config=None, payload=self.payload(), context=context)

            self.assertTrue(any(
                event["type"] == "runner_process_failed" and event["exit_code"] == 7
                for event in events
            ))

    def test_codex_spawn_error_is_executor_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []

            def fake_popen(args, **kwargs):
                raise OSError("missing binary")

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                popen_factory=fake_popen,
                which=lambda command: command,
            )
            context = make_context("run-spawn-error", os.path.join(tmpdir, "run-spawn-error"), events)

            with self.assertRaisesRegex(Exception, "failed to start codex exec"):
                executor.start(config=None, payload=self.payload(), context=context)
```

- [x] **Step 3: Run RED**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: timeout test fails because `subprocess.TimeoutExpired` is not caught and no `runner_timeout` event is emitted.

- [x] **Step 4: Implement timeout handling**

In `CodexExecExecutor.start()`, replace:

```python
        return_code = process.wait(timeout=self.timeout_seconds)
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
```

with:

```python
        try:
            return_code = process.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            context.emit_event(
                "runner_timeout",
                source=self.id,
                timeout_seconds=self.timeout_seconds,
            )
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
            raise ExecutorError("codex exec timed out")

        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
```

- [x] **Step 5: Run GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_executors
```

Expected: all tests pass.

- [x] **Step 6: Commit Task 5**

Run:

```bash
git add game_reverse/executors.py tests/test_game_reverse_executors.py
git commit -m "Handle Codex exec runtime failures"
```

Expected: commit succeeds.

## Task 6: Web Service Codex Integration With Fake Process

**Files:**
- Modify: `tests/test_game_reverse_web_service.py`

- [x] **Step 1: Write Web service fake Codex test**

In `tests/test_game_reverse_web_service.py`, add imports:

```python
from game_reverse.executors import CodexExecExecutor, ExecutorRegistry
```

Add this test:

```python
    def test_web_service_runs_enabled_codex_executor_with_fake_process(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        def fake_popen(args, **kwargs):
            final_path = args[args.index("--output-last-message") + 1]
            with open(final_path, "w", encoding="utf-8") as last_message:
                last_message.write("Codex completed through service")
            return FakeServiceProcess(
                stdout_lines=['{"type": "assistant_message", "message": "service event"}\n'],
                stderr_lines=[],
                returncode=0,
            )

        codex_executor = CodexExecExecutor(
            project_root=os.getcwd(),
            enabled=True,
            popen_factory=fake_popen,
            which=lambda command: command,
        )
        registry = ExecutorRegistry([codex_executor])
        service = GameReverseWebService(
            output_root=self.tmpdir.name,
            runner=FakeRunner(),
            executors=registry,
        )
        payload = self.valid_payload()
        payload["runner"] = "codex_exec"

        result = service.start_run(payload)
        completed = self.wait_for_status(service, result["id"], "completed")

        self.assertEqual(completed["runner"], "codex_exec")
        self.assertTrue(os.path.exists(os.path.join(completed["session_dir"], "final_report.md")))
        events = service.run_events(result["id"])
        self.assertTrue(any(event.get("message") == "service event" for event in events))
        report = service.session_report(result["id"])
        self.assertIn("Codex completed through service", report["final_report"])
```

Add the helper fake process above `TestGameReverseWebService`:

```python
class FakeServiceProcess:
    def __init__(self, stdout_lines=None, stderr_lines=None, returncode=0):
        self.stdout = stdout_lines or []
        self.stderr = stderr_lines or []
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        pass

    def kill(self):
        pass
```

- [x] **Step 2: Run RED or GREEN**

Run:

```bash
python -m unittest tests.test_game_reverse_web_service
```

Expected: pass if Tasks 1-5 already cover the integration path. If it fails, fix only the integration mismatch shown by this test.

- [x] **Step 3: Commit Task 6**

Run:

```bash
git add tests/test_game_reverse_web_service.py
git commit -m "Cover Codex web service execution"
```

Expected: commit succeeds.

## Task 7: Full Verification

**Files:**
- Verify only unless failures require fixes.

- [x] **Step 1: Run focused backend tests**

Run:

```bash
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service tests.test_game_reverse_web_server
```

Expected: all tests pass.

- [x] **Step 2: Run existing project-focused suite**

Run:

```bash
python -m unittest tests.test_game_reverse_executors tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor tests.test_game_reverse_config tests.test_game_reverse_journal tests.test_game_reverse_llm_decider tests.test_game_reverse_mission tests.test_game_reverse_report_writer tests.test_game_reverse_run_loop
```

Expected: all tests pass.

- [x] **Step 3: Run JavaScript syntax check**

Run:

```bash
node --check web/app.js
```

Expected: exit code 0.

- [x] **Step 4: Check local Codex CLI remains discoverable**

Run:

```bash
codex --version
codex exec --help
```

Expected: `codex-cli 0.139.0` or newer, and help output includes `--cd`, `--json`, and `--output-last-message`.

- [x] **Step 5: Check diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors and only intended files changed.

## Task 8: Documentation Note And Final Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-06-17-codex-exec-runner.md`

- [x] **Step 1: Mark completed plan boxes**

As each implementation task completes, change that task's executed checkboxes from:

```markdown
- [ ] **Step N: ...
```

to:

```markdown
- [x] **Step N: ...
```

Only mark steps that were actually executed.

- [x] **Step 2: Commit plan status**

Run:

```bash
git add docs/superpowers/plans/2026-06-17-codex-exec-runner.md
git commit -m "Track Codex exec runner implementation"
```

Expected: commit succeeds if the plan checklist changed during implementation.

## Operator Run After Implementation

After tests pass, start the backend with Codex enabled:

```powershell
$env:GAME_REVERSE_ENABLE_CODEX_EXEC = "1"
$env:GAME_REVERSE_CODEX_TIMEOUT_SECONDS = "900"
python -m game_reverse.web_server --host 127.0.0.1 --port 8768
```

Open:

```text
http://127.0.0.1:8768/web/index.html
```

The API can then start a Codex runner with payload `runner: "codex_exec"`. Keep `allowed_actions` limited to `screenshot`, `wait`, and `back` until the operator explicitly enables unsafe actions for real device control.
