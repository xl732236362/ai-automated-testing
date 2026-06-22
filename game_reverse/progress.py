# -*- coding: utf-8 -*-
"""Verified gameplay progress extraction and comparison."""


def normalize_progress(raw):
    if not isinstance(raw, dict):
        return {}

    counts = _normalize_counts(raw.get("target_counts"))
    return {
        "level_label": str(raw.get("level_label") or ""),
        "target_counts": counts,
        "terminal_state": str(raw.get("terminal_state") or ""),
    }


def compare_progress(before, after):
    before = normalize_progress(before)
    after = normalize_progress(after)
    before_counts = before.get("target_counts") or []
    after_counts = after.get("target_counts") or []
    if not before_counts and not after_counts and not after.get("terminal_state"):
        return {}
    progress_delta = _progress_delta(before_counts, after_counts)
    return {
        "before_counts": before_counts,
        "after_counts": after_counts,
        "progress_delta": progress_delta,
        "changed": bool(before_counts and after_counts and before_counts != after_counts),
        "level_before": before.get("level_label", ""),
        "level_after": after.get("level_label", ""),
        "terminal_state": after.get("terminal_state", ""),
    }


def _normalize_counts(value):
    if not isinstance(value, list):
        return []
    counts = []
    for item in value:
        try:
            count = int(item)
        except (TypeError, ValueError):
            return []
        if count < 0:
            return []
        counts.append(count)
    return counts


def _progress_delta(before_counts, after_counts):
    if not before_counts or not after_counts or len(before_counts) != len(after_counts):
        return 0
    return sum(max(0, before - after) for before, after in zip(before_counts, after_counts))
