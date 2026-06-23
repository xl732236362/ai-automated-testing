# -*- coding: utf-8 -*-
"""Reusable skill library for game_reverse exploration."""

from copy import deepcopy

from game_reverse.actions import validate_action


SKILL_SCHEMA_VERSION = 1
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
SUCCESS_SIGNALS = {
    "level_started",
    "popup_closed",
    "level_completed",
    "state_changed",
    "entered_new_state",
    "counter_changed",
}


class SkillLibrary:
    def __init__(self, skills=None, confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD):
        self.skills = [_normalize_skill(skill) for skill in (skills or [])]
        self.confidence_threshold = confidence_threshold

    def best_match(self, observation, affordances=None):
        labels = _observation_labels(observation)
        matches = []
        for skill in self.skills:
            if skill.get("type") == "continuous_control":
                continue
            if skill["confidence"] < self.confidence_threshold:
                continue
            trigger = skill.get("trigger", {})
            trigger_labels = set(trigger.get("state_labels", []))
            if trigger_labels and trigger_labels.isdisjoint(labels):
                continue
            required_affordance = trigger.get("required_affordance")
            if required_affordance and not _has_affordance(affordances, required_affordance):
                continue
            matches.append(skill)
        if not matches:
            return None
        matches.sort(key=lambda item: (-item["confidence"], item["name"]))
        return matches[0]

    def replay(self, skill, executor, screen_path, screen_size, allowed_actions):
        attempt = {
            "skill_name": skill["name"],
            "success": False,
            "steps_attempted": 0,
            "error": "",
        }
        try:
            for raw_step in skill.get("steps", []):
                action = validate_action(raw_step, allowed_actions, screen_size)
                executor.execute(action, screen_path)
                attempt["steps_attempted"] += 1
        except Exception as exc:
            attempt["error"] = str(exc)
            self.record_attempt(skill["name"], success=False)
            return attempt

        attempt["success"] = True
        self.record_attempt(skill["name"], success=True)
        return attempt

    def record_attempt(self, skill_name, success):
        skill = self._find(skill_name)
        if skill is None:
            return None
        skill["run_count"] = skill.get("run_count", 0) + 1
        if success:
            skill["success_count"] = skill.get("success_count", 0) + 1
            skill["confidence"] = min(1.0, round(skill.get("confidence", 0.5) + 0.1, 3))
        else:
            skill["failure_count"] = skill.get("failure_count", 0) + 1
            skill["confidence"] = max(0.0, round(skill.get("confidence", 0.5) - 0.2, 3))
        return skill

    def mine_candidates(self, action_records):
        candidates = []
        for record in action_records or []:
            feedback_result = record.get("feedback_result")
            if feedback_result not in SUCCESS_SIGNALS:
                continue
            state = record.get("state") or record.get("state_id") or "unknown"
            action = record.get("action")
            if not action or action.get("type") == "error":
                continue
            if action.get("type") == "aim_fire" and record.get("control_feedback") == "target_collected":
                candidates.append(_continuous_control_skill(record, action))
                continue
            candidates.append(
                _normalize_skill(
                    {
                        "name": "skill_from_%s_to_%s" % (_slug(state), feedback_result),
                        "trigger": {"state_labels": [state]},
                        "steps": [deepcopy(action)],
                        "success_signal": feedback_result,
                        "failure_signal": "no_visible_change",
                        "confidence": 0.55,
                        "run_count": 0,
                    }
                )
            )
        return candidates

    def to_skills(self):
        return {"version": SKILL_SCHEMA_VERSION, "skills": deepcopy(self.skills)}

    def _find(self, skill_name):
        for skill in self.skills:
            if skill["name"] == skill_name:
                return skill
        return None


def _normalize_skill(skill):
    normalized = deepcopy(skill)
    normalized.setdefault("name", "unnamed_skill")
    normalized.setdefault("type", "action_sequence")
    normalized.setdefault("trigger", {})
    normalized.setdefault("steps", [])
    normalized.setdefault("success_signal", "")
    normalized.setdefault("failure_signal", "no_visible_change")
    normalized.setdefault("confidence", 0.5)
    normalized.setdefault("run_count", 0)
    normalized.setdefault("success_count", 0)
    normalized.setdefault("failure_count", 0)
    return normalized


def _continuous_control_skill(record, action):
    state = record.get("state") or record.get("state_id") or "unknown"
    target = action.get("target") or {}
    control = action.get("control") or {}
    cursor = action.get("cursor") or {}
    return _normalize_skill(
        {
            "name": "continuous_%s_to_target_collected" % _slug(state),
            "type": "continuous_control",
            "controller": "aim_fire",
            "trigger": {"state_labels": [state]},
            "steps": [],
            "parameters": {
                "control_role": control.get("role", ""),
                "cursor_role": cursor.get("role", ""),
                "target_role": target.get("role", ""),
                "target_label": target.get("label", ""),
            },
            "success_signal": "target_collected",
            "failure_signal": "control_attempt_failed",
            "confidence": 0.55,
            "run_count": 0,
        }
    )


def _observation_labels(observation):
    observation = observation or {}
    labels = set(observation.get("state_labels", []) or [])
    if observation.get("state"):
        labels.add(observation["state"])
    if observation.get("state_id"):
        labels.add(observation["state_id"])
    return labels


def _has_affordance(affordances, label):
    for item in affordances or []:
        if item.get("label") == label or item.get("id") == label:
            return True
    return False


def _slug(value):
    return "_".join(str(value or "unknown").lower().split())
