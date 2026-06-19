# -*- coding: utf-8 -*-
"""Read-only profile summaries for the web console."""

import json
import os

from game_reverse.memory import sanitize_app_id


PROFILE_VIEW_VERSION = 1


def load_profile_summary(profile_root, package_name):
    app_id = sanitize_app_id(package_name)
    profile_dir = os.path.join(profile_root or "", app_id)
    exists = os.path.isdir(profile_dir)
    state_map = _read_json(profile_dir, "state_map.json", {"states": {}, "transitions": []})
    affordances = _read_json(profile_dir, "affordances.json", {"states": {}})
    skills = _read_json(profile_dir, "skills.json", {"skills": []})
    safety = _read_json(
        profile_dir,
        "safety_rules.json",
        {"sensitive_states": [], "interventions": []},
    )
    goals = _read_json(
        profile_dir,
        "goals.json",
        {
            "main_goal": "",
            "active_subgoal": "",
            "completed_subgoals": [],
            "blocked_subgoals": [],
            "next_candidates": [],
        },
    )
    recent_memory = _read_memory(profile_dir, "memory.jsonl")
    states = _state_rows(state_map)

    return {
        "version": PROFILE_VIEW_VERSION,
        "exists": exists,
        "package_name": package_name,
        "app_id": app_id,
        "profile_dir": profile_dir if exists else "",
        "current_state": states[0] if states else {},
        "states": states,
        "transitions": _transition_rows(state_map),
        "affordances": _affordance_rows(affordances),
        "skills": _skill_rows(skills),
        "safety": {
            "sensitive_states": list(safety.get("sensitive_states", [])),
            "interventions": list(safety.get("interventions", []))[-20:],
        },
        "goals": goals,
        "memory_summary": {
            "event_count": len(recent_memory),
            "latest_event": recent_memory[-1] if recent_memory else {},
        },
        "recent_memory": recent_memory[-20:],
    }


def _read_json(profile_dir, filename, default):
    path = os.path.join(profile_dir, filename)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as json_file:
        return json.load(json_file)


def _read_memory(profile_dir, filename):
    path = os.path.join(profile_dir, filename)
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as memory_file:
        for line in memory_file:
            if line.strip():
                records.append(json.loads(line))
    return records


def _state_rows(state_map):
    states = []
    for state_id, state in (state_map.get("states") or {}).items():
        row = dict(state)
        row.setdefault("state_id", state_id)
        row.setdefault("label", "")
        row.setdefault("summary", "")
        row.setdefault("visit_count", 0)
        row.setdefault("last_seen_step", 0)
        row.setdefault("screenshot_tags", [])
        states.append(row)
    states.sort(key=lambda item: (-int(item.get("last_seen_step") or 0), item.get("state_id", "")))
    return states


def _transition_rows(state_map):
    transitions = list(state_map.get("transitions") or [])
    transitions.sort(key=lambda item: int(item.get("step") or 0), reverse=True)
    return transitions[:50]


def _affordance_rows(affordances):
    rows = []
    for state_id, items in (affordances.get("states") or {}).items():
        for item in items:
            row = dict(item)
            row.setdefault("state_id", state_id)
            row.setdefault("label", "")
            row.setdefault("confidence", 0)
            row.setdefault("last_result", "")
            row.setdefault("status", "")
            row.setdefault("supported_actions", [])
            rows.append(row)
    rows.sort(key=lambda item: (-float(item.get("confidence") or 0), item.get("label", "")))
    return rows[:100]


def _skill_rows(skills):
    rows = [dict(skill) for skill in skills.get("skills", []) or []]
    for row in rows:
        row.setdefault("name", "")
        row.setdefault("confidence", 0)
        row.setdefault("run_count", 0)
        row.setdefault("success_count", 0)
        row.setdefault("failure_count", 0)
        row.setdefault("trigger", {})
    rows.sort(key=lambda item: (-float(item.get("confidence") or 0), item.get("name", "")))
    return rows[:100]
