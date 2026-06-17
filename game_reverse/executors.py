# -*- coding: utf-8 -*-
"""Executor adapter boundary for game explorer runners."""

import json
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, field


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_PROMPT_KEYS = {"api_key", "authorization", "token", "secret", "password"}
REDACTED_VALUE = "[redacted]"
SECRET_KEY_PARTS = ("key", "token", "secret", "password", "authorization")
CODEX_STDOUT_FILENAME = "codex_stdout.jsonl"
CODEX_STDERR_FILENAME = "codex_stderr.log"
CODEX_LAST_MESSAGE_FILENAME = "codex_last_message.txt"
FINAL_REPORT_FILENAME = "final_report.md"


class ExecutorError(ValueError):
    """Raised when executor adapter input is invalid."""


class ExecutorUnavailableError(ExecutorError):
    """Raised when a known executor is intentionally disabled."""


@dataclass
class ExecutorRunContext:
    run_id: str
    run_dir: str
    emit_event: object


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

    def start(self, config, payload, context=None):
        return self.runner(config)


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
    description: str = (
        "Codex CLI runner is disabled. Set GAME_REVERSE_ENABLE_CODEX_EXEC=1 to enable it."
    )

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

    def build_prompt(self, payload, config):
        return build_runner_prompt(payload, self.id, config=config)

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

    def parse_events(self, lines):
        return parse_jsonl_events(lines, self.id, codex_message)

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

    def start(self, config, payload, context=None):
        raise ExecutorUnavailableError("runner is not available")

    def build_prompt(self, payload, config):
        return build_runner_prompt(payload, self.id, config=config)

    def build_command(self, prompt, repo_root=None):
        repo_root = validate_repo_root(repo_root or self.project_root, self.project_root)
        return ["claude", "-p", "--output-format", "stream-json", prompt]

    def parse_events(self, lines):
        return parse_jsonl_events(lines, self.id, claude_message)


class ExecutorRegistry:
    def __init__(self, executors):
        self.executors = {executor.id: executor for executor in executors}

    def metadata(self):
        return [self.executors[runner_id].metadata() for runner_id in self.executors]

    def get(self, runner_id):
        if runner_id not in self.executors:
            raise KeyError(runner_id)
        return self.executors[runner_id]


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
        "Allowed actions: %s" % ", ".join(allowed_actions),
        "Max steps: %s" % max_steps,
        "Stay within this repository.",
        "Use existing project tools and avoid unrelated code changes.",
        "Produce concise progress events and a final summary.",
    ]
    return "\n".join(lines)


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


def validate_repo_root(repo_root, project_root=PROJECT_ROOT):
    project_root = os.path.abspath(project_root)
    repo_root = os.path.abspath(repo_root)
    if os.path.commonpath([project_root, repo_root]) != project_root:
        raise ExecutorError("repo_root must stay inside project")
    return repo_root
