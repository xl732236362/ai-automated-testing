# -*- coding: utf-8 -*-
"""Persistent app profile memory for game_reverse."""

import json
import os
import re
import time


PROFILE_SCHEMA_VERSION = 1
SAFE_APP_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


class ProfileStore:
    def __init__(self, root, app_id):
        self.root = root
        self.app_id = sanitize_app_id(app_id)
        self.profile_dir = os.path.join(root, self.app_id)

    def initialize(self, package_name=None):
        os.makedirs(self.profile_dir, exist_ok=True)
        now = _timestamp()
        profile = self.load_json(
            "profile.json",
            {
                "schema_version": PROFILE_SCHEMA_VERSION,
                "app_id": self.app_id,
                "package_name": package_name or self.app_id,
                "first_seen": now,
                "last_seen": now,
                "operator_safety_settings": {},
            },
        )
        profile["schema_version"] = PROFILE_SCHEMA_VERSION
        profile.setdefault("app_id", self.app_id)
        profile["package_name"] = package_name or profile.get("package_name") or self.app_id
        profile.setdefault("first_seen", now)
        profile["last_seen"] = now
        profile.setdefault("operator_safety_settings", {})
        self.update_json("profile.json", profile)

        self._ensure_json("state_map.json", {"version": 1, "states": {}, "transitions": []})
        self._ensure_json("affordances.json", {"version": 1, "states": {}})
        self._ensure_json("safety_rules.json", {"version": 1, "sensitive_states": [], "interventions": []})
        self._ensure_json("skills.json", {"version": 1, "skills": []})
        self._ensure_json(
            "goals.json",
            {
                "version": 1,
                "main_goal": "",
                "active_subgoal": "",
                "completed_subgoals": [],
                "blocked_subgoals": [],
                "next_candidates": [],
            },
        )
        self._ensure_file("memory.jsonl")
        os.makedirs(os.path.join(self.profile_dir, "traces"), exist_ok=True)
        return self

    def load_json(self, filename, default):
        path = os.path.join(self.profile_dir, filename)
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as json_file:
            return json.load(json_file)

    def update_json(self, filename, payload):
        os.makedirs(self.profile_dir, exist_ok=True)
        path = os.path.join(self.profile_dir, filename)
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as json_file:
            json.dump(payload, json_file, ensure_ascii=False, indent=2, sort_keys=True)
            json_file.write("\n")
        _replace_with_retry(temp_path, path)

    def append_memory(self, event):
        os.makedirs(self.profile_dir, exist_ok=True)
        path = os.path.join(self.profile_dir, "memory.jsonl")
        record = dict(event)
        record.setdefault("timestamp", _timestamp())
        with open(path, "a", encoding="utf-8") as memory_file:
            memory_file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def append_trace(self, run_id, event):
        trace_dir = os.path.join(self.profile_dir, "traces")
        os.makedirs(trace_dir, exist_ok=True)
        safe_run_id = sanitize_app_id(run_id)
        path = os.path.join(trace_dir, "%s.jsonl" % safe_run_id)
        record = dict(event)
        record.setdefault("timestamp", _timestamp())
        with open(path, "a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _ensure_json(self, filename, default):
        path = os.path.join(self.profile_dir, filename)
        if not os.path.exists(path):
            self.update_json(filename, default)

    def _ensure_file(self, filename):
        path = os.path.join(self.profile_dir, filename)
        if not os.path.exists(path):
            open(path, "a", encoding="utf-8").close()


def sanitize_app_id(value):
    safe = SAFE_APP_ID_RE.sub("_", str(value or "unknown")).strip("._-")
    return safe or "unknown"


def _timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _replace_with_retry(source, destination, attempts=3, delay_seconds=0.05):
    last_error = None
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            time.sleep(delay_seconds)
    raise last_error
