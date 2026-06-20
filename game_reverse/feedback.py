# -*- coding: utf-8 -*-
"""Gameplay feedback classification helpers."""

COUNTER_KEYWORDS = ("counter", "count ", "changed from", "->", "数字", "计数")
TRAY_KEYWORDS = ("tray", "slot", "contains", "bottom", "托盘", "槽")
SENSITIVE_KEYWORDS = (
    "login",
    "log in",
    "account",
    "password",
    "payment",
    "purchase",
    "permission",
    "real-name",
    "credential",
    "登录",
    "账号",
    "密码",
    "支付",
    "购买",
    "权限",
    "实名",
)
POPUP_KEYWORDS = ("popup", "modal", "dialog", "弹窗", "对话框")
COMPLETED_KEYWORDS = ("level completed", "completed", "victory", "success", "reward", "通关", "胜利", "完成")
FAILED_KEYWORDS = ("level failed", "failed", "failure", "retry", "defeat", "失败", "重试")


def classify_feedback(before=None, after=None, before_screen_path=None, after_screen_path=None):
    before_text = _observation_text(before)
    after_text = _observation_text(after)
    visual_diff_score = _visual_diff_score(before, after, before_screen_path, after_screen_path)
    has_visual_evidence = _has_visual_evidence(before, after, before_screen_path, after_screen_path)
    ocr_changed = _text_items(before, "ocr") != _text_items(after, "ocr")
    ui_changed = _text_items(before, "ui_nodes") != _text_items(after, "ui_nodes")
    base = {
        "confidence": "medium",
        "visual_diff_score": visual_diff_score,
        "ocr_changed": ocr_changed,
        "ui_changed": ui_changed,
        "safety_label": "",
    }

    if _has_any(after_text, SENSITIVE_KEYWORDS):
        return _feedback(
            "sensitive_screen",
            _evidence(after_text, "sensitive screen"),
            base,
            confidence="high",
            safety_label="sensitive",
        )
    if _has_any(after_text, COMPLETED_KEYWORDS):
        return _feedback("level_completed", _evidence(after_text, "level completed"), base)
    if _has_any(after_text, FAILED_KEYWORDS):
        return _feedback("level_failed", _evidence(after_text, "level failed"), base)
    if _has_any(after_text, POPUP_KEYWORDS):
        return _feedback("popup_opened", _evidence(after_text, "popup opened"), base)
    if _has_counter_change(after_text) and before_text != after_text and not _unchanged_visual(has_visual_evidence, visual_diff_score):
        return _feedback("counter_changed", _evidence(after_text, "counter"), base)
    if _has_tray_change(after_text) and before_text != after_text and not _unchanged_visual(has_visual_evidence, visual_diff_score):
        return _feedback("tray_changed", _evidence(after_text, "tray"), base)
    if ocr_changed:
        return _feedback("ocr_changed", "OCR text changed", base)
    if ui_changed:
        return _feedback("ui_changed", "UI node text changed", base)
    if visual_diff_score > 0:
        return _feedback("visual_changed", "screenshot hash changed", base)
    return _feedback("no_visible_change", "screen summary unchanged", base, confidence="high")


def recommend_next_strategy(feedback_history):
    history = list(feedback_history or [])
    last = history[-1] if history else {}
    if last.get("result") == "sensitive_screen":
        return {
            "next_strategy": "back_or_wait_only",
            "recommended_actions": ["back", "wait"],
            "reason": "sensitive screen detected",
        }
    if last.get("result") == "level_failed":
        return {
            "next_strategy": "recover_from_failure",
            "recommended_actions": ["back", "wait"],
            "reason": "failure screen detected",
        }

    recent_three = history[-3:]
    if (
        len(recent_three) >= 3
        and all(item.get("result") == "no_visible_change" for item in recent_three)
        and len({item.get("state_id") for item in recent_three}) == 1
        and len({item.get("action_type") for item in recent_three}) == 1
    ):
        return {
            "next_strategy": "switch_target",
            "recommended_actions": ["tap", "swipe", "hold_drag_release"],
            "reason": "loop detected from repeated no-change feedback",
        }

    recent = history[-2:]
    if len(recent) >= 2 and all(item.get("result") == "no_visible_change" for item in recent):
        return {
            "next_strategy": "switch_gesture",
            "recommended_actions": ["swipe", "hold_drag_release"],
            "reason": "repeated no-change feedback",
        }
    return {"next_strategy": "continue", "recommended_actions": [], "reason": ""}


def _observation_text(observation):
    if not observation:
        return ""
    parts = [
        str(observation.get(key, ""))
        for key in ("screen_summary", "state", "result")
        if observation.get(key)
    ]
    parts.extend(_text_items(observation, "ocr"))
    parts.extend(_text_items(observation, "ui_nodes"))
    return " ".join(parts).lower()


def _has_counter_change(text):
    return any(keyword in text for keyword in COUNTER_KEYWORDS)


def _has_tray_change(text):
    return any(keyword in text for keyword in TRAY_KEYWORDS)


def _has_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def _evidence(text, fallback):
    return text[:240] if text else fallback


def _feedback(result, evidence, base, confidence=None, safety_label=None):
    feedback = dict(base)
    feedback["result"] = result
    feedback["evidence"] = evidence
    if confidence is not None:
        feedback["confidence"] = confidence
    if safety_label is not None:
        feedback["safety_label"] = safety_label
    return feedback


def _text_items(observation, key):
    if not observation:
        return []
    items = observation.get(key, []) or []
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append(item.lower())
        elif isinstance(item, dict):
            normalized.append(
                " ".join(
                    str(item.get(field, "")).lower()
                    for field in ("text", "content_desc", "class")
                    if item.get(field)
                )
            )
    return sorted(value for value in normalized if value)


def _visual_diff_score(before, after, before_screen_path, after_screen_path):
    if before_screen_path and after_screen_path:
        try:
            with open(before_screen_path, "rb") as before_file:
                before_bytes = before_file.read()
            with open(after_screen_path, "rb") as after_file:
                after_bytes = after_file.read()
        except OSError:
            return 0.0
        return 0.0 if before_bytes == after_bytes else 1.0
    before_hash = (before or {}).get("screenshot_hash")
    after_hash = (after or {}).get("screenshot_hash")
    if before_hash and after_hash:
        return 0.0 if before_hash == after_hash else 1.0
    return 0.0


def _has_visual_evidence(before, after, before_screen_path, after_screen_path):
    return bool(
        ((before or {}).get("screenshot_hash") and (after or {}).get("screenshot_hash"))
        or (before_screen_path and after_screen_path)
    )


def _unchanged_visual(has_visual_evidence, visual_diff_score):
    return has_visual_evidence and visual_diff_score == 0.0
