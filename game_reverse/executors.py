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
        raise ExecutorUnavailableError("runner is not available")

    def build_prompt(self, payload, config):
        return build_runner_prompt(payload, self.id)

    def build_command(self, prompt, repo_root=None):
        repo_root = validate_repo_root(repo_root or self.project_root, self.project_root)
        return ["codex", "exec", "--cd", repo_root, "--json", prompt]

    def parse_events(self, lines):
        return parse_jsonl_events(lines, self.id, codex_message)


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
        return build_runner_prompt(payload, self.id)

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
