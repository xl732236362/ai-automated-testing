# -*- coding: utf-8 -*-
"""Run-local state graph tracking for game_reverse sessions."""

import hashlib


STATE_GRAPH_VERSION = 1


class StateGraph:
    def __init__(self):
        self.states = {}
        self.transitions = []
        self._signature_to_state_id = {}
        self._previous_state_id = None

    def update(self, step, screen_path, observation, screenshot_hash=None):
        signature = _state_signature(observation, screenshot_hash)
        state_id = self._signature_to_state_id.get(signature)
        is_new_state = state_id is None
        if is_new_state:
            state_id = _state_id(signature)
            self._signature_to_state_id[signature] = state_id
            self.states[state_id] = _new_state_record(
                state_id,
                signature,
                step,
                screen_path,
                observation,
                screenshot_hash,
            )
        else:
            _update_state_record(self.states[state_id], step)

        transition = {
            "step": step,
            "from_state_id": self._previous_state_id,
            "to_state_id": state_id,
            "classification": _classify_transition(self._previous_state_id, state_id, is_new_state),
            "screen": screen_path,
        }
        self.transitions.append(transition)
        self._previous_state_id = state_id

        return {
            "state_id": state_id,
            "state_visit_count": self.states[state_id]["visit_count"],
            "transition": dict(transition),
        }

    def to_state_map(self):
        return {
            "version": STATE_GRAPH_VERSION,
            "states": dict(sorted(self.states.items())),
            "transitions": list(self.transitions),
        }


def _state_signature(observation, screenshot_hash=None):
    observation = observation or {}
    parts = []
    if screenshot_hash:
        parts.append("hash:%s" % screenshot_hash)
    else:
        parts.extend(
            [
                "state:%s" % _normalize_text(observation.get("state", "")),
                "summary:%s" % _normalize_text(observation.get("screen_summary", "")),
                "tags:%s" % ",".join(sorted(_normalize_text(tag) for tag in observation.get("screenshot_tags", []))),
            ]
        )
    return "|".join(parts)


def _state_id(signature):
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:12]
    return "state_%s" % digest


def _new_state_record(state_id, signature, step, screen_path, observation, screenshot_hash):
    return {
        "state_id": state_id,
        "signature": signature,
        "label": observation.get("state", "unknown"),
        "summary": observation.get("screen_summary", ""),
        "representative_screen": screen_path,
        "screenshot_hash": screenshot_hash,
        "first_seen_step": step,
        "last_seen_step": step,
        "visit_count": 1,
        "state_labels": list(observation.get("state_labels", [])),
        "screenshot_tags": list(observation.get("screenshot_tags", [])),
    }


def _update_state_record(record, step):
    record["last_seen_step"] = step
    record["visit_count"] += 1


def _classify_transition(previous_state_id, state_id, is_new_state):
    if previous_state_id is None:
        return "entered_new_state"
    if previous_state_id == state_id:
        return "no_change"
    if is_new_state:
        return "entered_new_state"
    return "state_changed"


def _normalize_text(value):
    return " ".join(str(value or "").lower().split())
