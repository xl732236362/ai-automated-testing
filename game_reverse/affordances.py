# -*- coding: utf-8 -*-
"""Run-local affordance discovery and feedback tracking."""

import hashlib


AFFORDANCE_VERSION = 1
NO_CHANGE_RESULTS = {"no_visible_change"}
SUCCESS_RESULTS = {"visual_changed", "state_changed", "entered_new_state", "counter_changed", "tray_changed"}


class AffordanceMemory:
    def __init__(self):
        self.states = {}

    def collect_from_observation(self, state_id, observation, screen_size=None):
        state_id = state_id or "unknown"
        candidates = self.states.setdefault(state_id, [])
        by_bucket = {_bucket_key(item): item for item in candidates}
        collected = []

        for raw in _iter_region_sources(observation or {}):
            normalized = _normalize_region(raw, state_id, screen_size)
            if normalized is None:
                continue
            key = _bucket_key(normalized)
            existing = by_bucket.get(key)
            if existing is None:
                by_bucket[key] = normalized
                candidates.append(normalized)
                collected.append(normalized)
            else:
                _merge_sources(existing, normalized)
                collected.append(existing)

        candidates.sort(key=lambda item: (-item["confidence"], item["bounds"], item["label"]))
        return list(candidates)

    def record_action_feedback(self, state_id, action, feedback_result):
        updated = []
        for item in self.states.get(state_id or "unknown", []):
            if not _action_hits_affordance(action or {}, item):
                continue
            item["tested_count"] += 1
            item["last_result"] = feedback_result
            if feedback_result in NO_CHANGE_RESULTS:
                item["confidence"] = max(0.0, round(item["confidence"] - 0.2, 3))
                item["status"] = "deprioritized"
            elif feedback_result in SUCCESS_RESULTS:
                item["confidence"] = min(1.0, round(item["confidence"] + 0.15, 3))
                item["status"] = "useful"
            else:
                item["status"] = "tested"
            updated.append(item)
        return updated

    def to_affordances(self):
        return {
            "version": AFFORDANCE_VERSION,
            "states": {state_id: list(items) for state_id, items in sorted(self.states.items())},
        }


def _iter_region_sources(observation):
    for item in observation.get("ocr", []) or []:
        yield {
            "source": "ocr",
            "bounds": item.get("bounds"),
            "label": item.get("text", ""),
            "supported_actions": ["tap"],
            "confidence": 0.75,
        }
    for item in observation.get("ui_nodes", []) or []:
        yield {
            "source": "ui_node",
            "bounds": item.get("bounds"),
            "label": item.get("text") or item.get("content_desc") or item.get("class", ""),
            "supported_actions": ["tap"],
            "confidence": 0.85,
        }
    for item in observation.get("visual_regions", []) or []:
        yield {
            "source": item.get("source", "visual"),
            "bounds": item.get("bounds"),
            "label": item.get("label") or item.get("reason", ""),
            "supported_actions": item.get("supported_actions", ["tap"]),
            "confidence": float(item.get("confidence", 0.55)),
        }
    for item in observation.get("proposed_regions", []) or []:
        yield {
            "source": item.get("source", "llm"),
            "bounds": item.get("bounds"),
            "label": item.get("label") or item.get("reason", ""),
            "supported_actions": item.get("supported_actions", ["tap"]),
            "confidence": float(item.get("confidence", 0.5)),
        }


def _normalize_region(raw, state_id, screen_size):
    bounds = _normalize_bounds(raw.get("bounds"), screen_size)
    if bounds is None:
        return None
    label = str(raw.get("label") or raw.get("source") or "region")
    supported_actions = list(raw.get("supported_actions") or ["tap"])
    record = {
        "id": _affordance_id(state_id, raw.get("source", "unknown"), bounds, supported_actions, label),
        "state_id": state_id,
        "bounds": bounds,
        "center": _center(bounds),
        "label": label,
        "sources": [raw.get("source", "unknown")],
        "supported_actions": supported_actions,
        "confidence": max(0.0, min(1.0, float(raw.get("confidence", 0.5)))),
        "tested_count": 0,
        "last_result": None,
        "status": "candidate",
    }
    return record


def _normalize_bounds(bounds, screen_size):
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        return None
    try:
        left, top, right, bottom = [int(round(float(value))) for value in bounds]
    except (TypeError, ValueError):
        return None
    if right <= left or bottom <= top:
        return None
    if left < 0 or top < 0:
        return None
    if screen_size is not None:
        width, height = screen_size
        if right > width or bottom > height:
            return None
    return [left, top, right, bottom]


def _bucket_key(item):
    left, top, right, bottom = item["bounds"]
    bucket = [round(value / 24.0) for value in (left, top, right, bottom)]
    return tuple(bucket)


def _merge_sources(existing, incoming):
    for source in incoming["sources"]:
        if source not in existing["sources"]:
            existing["sources"].append(source)
    for action in incoming["supported_actions"]:
        if action not in existing["supported_actions"]:
            existing["supported_actions"].append(action)
    if incoming["confidence"] > existing["confidence"]:
        existing["confidence"] = incoming["confidence"]
    if not existing["label"] and incoming["label"]:
        existing["label"] = incoming["label"]


def _action_hits_affordance(action, affordance):
    action_type = action.get("type")
    if action_type == "tap":
        return _point_in_bounds(action.get("x"), action.get("y"), affordance["bounds"])
    if action_type in ("swipe", "hold_drag_release"):
        return _point_in_bounds(action.get("x1"), action.get("y1"), affordance["bounds"])
    return False


def _point_in_bounds(x, y, bounds):
    if not isinstance(x, int) or not isinstance(y, int):
        return False
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


def _center(bounds):
    left, top, right, bottom = bounds
    return [int((left + right) / 2), int((top + bottom) / 2)]


def _affordance_id(state_id, source, bounds, supported_actions, label):
    payload = "%s|%s|%s|%s|%s" % (
        state_id,
        source,
        ",".join(str(value) for value in bounds),
        ",".join(sorted(supported_actions)),
        label,
    )
    return "aff_%s" % hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
