# -*- coding: utf-8 -*-
"""Cross-session profile merge and prompt memory helpers."""

from copy import deepcopy


def merge_profile_payloads(
    existing_state_map,
    current_state_map,
    existing_affordances,
    current_affordances,
    existing_skills,
    mined_skills,
    session_name,
):
    return {
        "state_map": merge_state_maps(existing_state_map, current_state_map, session_name),
        "affordances": merge_affordances(existing_affordances, current_affordances),
        "skills": merge_skills(existing_skills, mined_skills),
    }


def merge_state_maps(existing, current, session_name):
    existing = deepcopy(existing or {"version": 1, "states": {}, "transitions": []})
    current = current or {"version": 1, "states": {}, "transitions": []}
    states = existing.setdefault("states", {})

    for state_id, incoming in (current.get("states") or {}).items():
        if state_id not in states:
            states[state_id] = deepcopy(incoming)
            continue
        _merge_state_record(states[state_id], incoming)

    transitions = existing.setdefault("transitions", [])
    seen = {_transition_key(item) for item in transitions}
    for transition in current.get("transitions") or []:
        item = dict(transition)
        item.setdefault("session_name", session_name)
        key = _transition_key(item)
        if key not in seen:
            transitions.append(item)
            seen.add(key)

    existing["version"] = 1
    return existing


def merge_affordances(existing, current):
    existing = deepcopy(existing or {"version": 1, "states": {}})
    current = current or {"version": 1, "states": {}}
    states = existing.setdefault("states", {})
    for state_id, items in (current.get("states") or {}).items():
        merged = {_affordance_key(item): dict(item) for item in states.get(state_id, [])}
        for item in items or []:
            key = _affordance_key(item)
            if key not in merged or float(item.get("confidence") or 0) > float(merged[key].get("confidence") or 0):
                merged[key] = dict(item)
        states[state_id] = list(merged.values())
    existing["version"] = 1
    return existing


def merge_skills(existing, mined_skills):
    existing = deepcopy(existing or {"version": 1, "skills": []})
    skills = {skill.get("name", ""): dict(skill) for skill in existing.get("skills", []) if skill.get("name")}
    for candidate in mined_skills or []:
        name = candidate.get("name")
        if not name:
            continue
        if name not in skills:
            skills[name] = dict(candidate)
            continue
        skills[name] = _merge_skill_record(skills[name], candidate)
    return {"version": 1, "skills": sorted(skills.values(), key=lambda item: item.get("name", ""))}


def summarize_profile_memory(profile, max_lines=8):
    lines = []
    goals = profile.get("goals") or {}
    active_subgoal = goals.get("active_subgoal")
    if active_subgoal:
        lines.append("active_subgoal: %s" % active_subgoal)

    for skill in _top_skills(_profile_skills(profile), limit=3):
        lines.append(
            "skill: %s confidence=%.2f signal=%s"
            % (
                skill.get("name", ""),
                float(skill.get("confidence") or 0),
                skill.get("success_signal", ""),
            )
        )

    for item in (profile.get("recent_memory") or [])[-3:]:
        action_type = (item.get("action") or {}).get("type", "")
        feedback_result = item.get("feedback_result", "")
        if action_type or feedback_result:
            lines.append("memory: %s -> %s" % (action_type or "action", feedback_result or "unknown"))

    return "\n".join(lines[:max_lines])


def _profile_skills(profile):
    skills = (profile or {}).get("skills") or []
    if isinstance(skills, dict):
        return skills.get("skills", [])
    return skills


def _merge_state_record(existing, incoming):
    existing["visit_count"] = int(existing.get("visit_count") or 0) + int(incoming.get("visit_count") or 0)
    existing["last_seen_step"] = max(int(existing.get("last_seen_step") or 0), int(incoming.get("last_seen_step") or 0))
    existing["first_seen_step"] = min(
        int(existing.get("first_seen_step") or incoming.get("first_seen_step") or 0),
        int(incoming.get("first_seen_step") or existing.get("first_seen_step") or 0),
    )
    for key in ("label", "summary", "representative_screen", "screenshot_hash"):
        if incoming.get(key):
            existing[key] = incoming[key]
    existing["screenshot_tags"] = sorted(
        set(existing.get("screenshot_tags") or []) | set(incoming.get("screenshot_tags") or [])
    )
    existing["state_labels"] = sorted(
        set(existing.get("state_labels") or []) | set(incoming.get("state_labels") or [])
    )


def _merge_skill_record(existing, incoming):
    merged = dict(existing)
    merged["confidence"] = max(float(existing.get("confidence") or 0), float(incoming.get("confidence") or 0))
    merged["run_count"] = int(existing.get("run_count") or 0) + int(incoming.get("run_count") or 0)
    merged["success_count"] = int(existing.get("success_count") or 0) + int(incoming.get("success_count") or 0)
    merged["failure_count"] = int(existing.get("failure_count") or 0) + int(incoming.get("failure_count") or 0)
    if not merged.get("steps") and incoming.get("steps"):
        merged["steps"] = deepcopy(incoming["steps"])
    return merged


def _top_skills(skills, limit):
    return sorted(skills or [], key=lambda item: (-float(item.get("confidence") or 0), item.get("name", "")))[:limit]


def _transition_key(item):
    return (
        item.get("session_name", ""),
        item.get("step"),
        item.get("from_state_id"),
        item.get("to_state_id"),
        item.get("classification"),
    )


def _affordance_key(item):
    return item.get("id") or item.get("label") or str(item.get("bounds") or item)
