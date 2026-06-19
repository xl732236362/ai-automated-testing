# -*- coding: utf-8 -*-
"""Gameplay feedback classification helpers."""

COUNTER_KEYWORDS = ("counter", "count", "changed from", "->", "变", "计数")
TRAY_KEYWORDS = ("tray", "slot", "contains", "bottom", "托盘", "槽")


def classify_feedback(before=None, after=None):
    before_text = _observation_text(before)
    after_text = _observation_text(after)
    if _has_counter_change(after_text) and before_text != after_text:
        return {"result": "counter_changed", "evidence": _evidence(after_text, "counter")}
    if _has_tray_change(after_text) and before_text != after_text:
        return {"result": "tray_changed", "evidence": _evidence(after_text, "tray")}
    return {"result": "no_visible_change", "evidence": "screen summary unchanged"}


def recommend_next_strategy(feedback_history):
    recent = list(feedback_history or [])[-2:]
    if len(recent) >= 2 and all(item.get("result") == "no_visible_change" for item in recent):
        return {
            "next_strategy": "switch_gesture",
            "recommended_actions": ["swipe", "hold_drag_release"],
        }
    return {"next_strategy": "continue", "recommended_actions": []}


def _observation_text(observation):
    if not observation:
        return ""
    return " ".join(
        str(observation.get(key, ""))
        for key in ("screen_summary", "state", "result")
        if observation.get(key)
    ).lower()


def _has_counter_change(text):
    return any(keyword in text for keyword in COUNTER_KEYWORDS)


def _has_tray_change(text):
    return any(keyword in text for keyword in TRAY_KEYWORDS)


def _evidence(text, fallback):
    return text[:240] if text else fallback
