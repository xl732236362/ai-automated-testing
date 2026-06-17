# -*- coding: utf-8 -*-
"""Local service boundary for the game explorer web console."""

import os
import threading
import time

from game_reverse.config import DEFAULT_ALLOWED_ACTIONS, GameReverseConfig
from game_reverse.mission import parse_mission
from game_reverse.run_loop import run_loop


UNSAFE_ACTIONS = {"tap", "swipe"}


class ValidationError(ValueError):
    """Raised when a web API payload is invalid or unsafe."""


class GameReverseWebService:
    def __init__(self, output_root=None, runner=None):
        self.output_root = output_root or "game_reverse/outputs/sessions"
        self.runner = runner or run_loop
        self.runs = {}
        self.events = {}
        self.lock = threading.Lock()
        self.run_counter = 0

    def health(self):
        return {
            "status": "ok",
            "static_only": False,
            "runners": [
                {
                    "id": "game_reverse",
                    "name": "game_reverse",
                    "available": True,
                    "description": "Run the local game_reverse loop with validated config.",
                },
                {
                    "id": "codex_exec",
                    "name": "Codex CLI",
                    "available": False,
                    "description": "Planned executor adapter; not enabled in this phase.",
                },
                {
                    "id": "claude_print",
                    "name": "ClaudeCode CLI",
                    "available": False,
                    "description": "Planned executor adapter; not enabled in this phase.",
                },
            ],
        }

    def config(self):
        return {
            "output_root": self.output_root,
            "default_allowed_actions": list(DEFAULT_ALLOWED_ACTIONS),
            "unsafe_actions": sorted(UNSAFE_ACTIONS),
        }

    def start_run(self, payload):
        config = self._config_from_payload(payload)
        run_id = self._next_run_id()
        record = {
            "id": run_id,
            "runner": "game_reverse",
            "status": "queued",
            "session_dir": None,
            "started_at": run_id,
        }
        with self.lock:
            self.runs[run_id] = record
            self.events[run_id] = []
            self._append_event_locked(run_id, "run_queued")

        thread = threading.Thread(target=self._run_background, args=(run_id, config))
        thread.daemon = True
        thread.start()

        return dict(record)

    def get_run(self, run_id):
        with self.lock:
            if run_id not in self.runs:
                raise KeyError(run_id)
            return dict(self.runs[run_id])

    def run_events(self, run_id):
        with self.lock:
            if run_id not in self.events:
                raise KeyError(run_id)
            return [dict(event) for event in self.events[run_id]]

    def list_sessions(self):
        if not os.path.isdir(self.output_root):
            return []

        sessions = []
        for name in sorted(os.listdir(self.output_root), reverse=True):
            session_dir = os.path.join(self.output_root, name)
            if os.path.isdir(session_dir):
                sessions.append(
                    {
                        "id": name,
                        "session_dir": session_dir,
                        "has_final_report": os.path.exists(
                            os.path.join(session_dir, "final_report.md")
                        ),
                    }
                )
        return sessions

    def session_report(self, session_id):
        session_dir = None
        try:
            record = self.get_run(session_id)
            session_dir = record.get("session_dir")
        except KeyError:
            candidate = os.path.join(self.output_root, session_id)
            if os.path.isdir(candidate):
                session_dir = candidate

        if not session_dir:
            raise FileNotFoundError(session_id)

        return {
            "id": session_id,
            "session_dir": session_dir,
            "mission_draft": self._read_optional(session_dir, "mission_draft.md"),
            "final_report": self._read_optional(session_dir, "final_report.md"),
            "actions": self._read_optional(session_dir, "actions.jsonl"),
            "observations": self._read_optional(session_dir, "observations.jsonl"),
        }

    def _config_from_payload(self, payload):
        if not isinstance(payload, dict):
            raise ValidationError("payload must be an object")

        runner = payload.get("runner", "game_reverse")
        if runner != "game_reverse":
            raise ValidationError("runner must be game_reverse in this phase")

        package_name = payload.get("package_name")
        if not package_name:
            raise ValidationError("package_name is required")

        max_steps = payload.get("max_steps", 50)
        if not isinstance(max_steps, int) or max_steps <= 0:
            raise ValidationError("max_steps must be a positive int")

        allowed_actions = list(payload.get("allowed_actions") or DEFAULT_ALLOWED_ACTIONS)
        if UNSAFE_ACTIONS.intersection(allowed_actions) and not payload.get(
            "enable_unsafe_actions"
        ):
            raise ValidationError("enable_unsafe_actions is required for tap or swipe")

        return GameReverseConfig(
            device_uri=payload.get("device_uri", "Android:///"),
            package_name=package_name,
            max_steps=max_steps,
            mission=parse_mission(payload.get("mission")),
            model=payload.get("model", "claude-opus-4-8"),
            output_root=payload.get("output_root", self.output_root),
            allowed_actions=allowed_actions,
            recent_steps=payload.get("recent_steps", 5),
            llm_retry_count=payload.get("llm_retry_count", 1),
            consecutive_failure_limit=payload.get("consecutive_failure_limit", 3),
        )

    def _next_run_id(self):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        with self.lock:
            self.run_counter += 1
            return "%s-%03d" % (timestamp, self.run_counter)

    def _run_background(self, run_id, config):
        with self.lock:
            record = self.runs[run_id]
            record["status"] = "running"
            self._append_event_locked(run_id, "run_started")

        try:
            session_dir = self.runner(config)
        except Exception as exc:
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

        with self.lock:
            record = self.runs[run_id]
            record.update({"status": "completed", "session_dir": session_dir})
            self._append_event_locked(run_id, "run_completed", session_dir=session_dir)

    def _append_event_locked(self, run_id, event_type, **extra):
        event = {
            "type": event_type,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        event.update(extra)
        self.events[run_id].append(event)

    def _read_optional(self, session_dir, filename):
        path = os.path.join(session_dir, filename)
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as report_file:
            return report_file.read()
