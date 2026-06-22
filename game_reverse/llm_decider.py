# -*- coding: utf-8 -*-
"""Claude decision parsing and runtime client boundary."""

import base64
import json
import os
import re
from pathlib import Path


REQUIRED_DECISION_FIELDS = [
    "screen_summary",
    "state",
    "action",
    "reason",
    "new_findings",
    "screenshot_tags",
    "risks",
]
MAX_PROMPT_RECENT_ACTIONS = 5
MAX_MISSION_DRAFT_CHARS = 2000


def parse_decision(text):
    try:
        decision = json.loads(_extract_json_text(text))
    except ValueError as exc:
        raise ValueError("Claude decision must be valid JSON: %s" % _response_preview(text)) from exc
    if not isinstance(decision, dict):
        raise ValueError("Claude decision must be an object")
    _fill_decision_defaults(decision)
    if "action" not in decision:
        raise ValueError("Claude decision missing action: %s" % _response_preview(text))
    if not isinstance(decision["action"], dict):
        raise ValueError("Claude decision action must be an object")
    return decision


def _extract_json_text(text):
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _fill_decision_defaults(decision):
    decision.setdefault("screen_summary", "")
    decision.setdefault("state", "unknown")
    decision.setdefault("reason", "")
    decision.setdefault("new_findings", [])
    decision.setdefault("screenshot_tags", [])
    decision.setdefault("risks", [])
    decision["new_findings"] = _normalize_findings(decision["new_findings"])


def _normalize_findings(findings):
    if not isinstance(findings, list):
        return []

    normalized = []
    for finding in findings:
        if isinstance(finding, str):
            normalized.append(
                {
                    "category": "finding",
                    "claim": finding,
                    "evidence": "",
                    "confidence": "medium",
                }
            )
        elif isinstance(finding, dict):
            normalized.append(
                {
                    "category": finding.get("category", "finding"),
                    "claim": finding.get("claim", ""),
                    "evidence": finding.get("evidence", ""),
                    "confidence": finding.get("confidence", "medium"),
                }
            )
    return normalized


def _response_preview(text):
    compact = " ".join(str(text).split())
    if len(compact) > 300:
        return compact[:300] + "..."
    return compact


class ClaudeDecider:
    def __init__(self, model):
        self.model = model

    def decide(self, screen_path, mission, recent_actions, mission_draft, memory_summary=""):
        client = _create_anthropic_client()
        with open(screen_path, "rb") as screen_file:
            image_data = base64.standard_b64encode(screen_file.read()).decode("utf-8")

        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": _build_decision_prompt(
                                mission,
                                recent_actions,
                                mission_draft,
                                memory_summary=memory_summary,
                            ),
                        },
                    ],
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": _decision_schema(),
                }
            },
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        return parse_decision(text)


def _create_anthropic_client():
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("Install the optional dependency with: pip install anthropic") from exc
    _load_project_env()
    return anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
    )


def _load_project_env(path=None):
    env_path = Path(path or ".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _unquote_env_value(value.strip())


def _unquote_env_value(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _build_decision_prompt(mission, recent_actions, mission_draft, memory_summary=""):
    return (
        "You are exploring an Android App/Game for authorized black-box testing, "
        "feature verification, or design analysis. Only recommend these actions: "
        "screenshot, wait, back, tap, swipe, hold_drag_release. For login, real-name verification, "
        "payment, permission grants, account/password entry, or other sensitive "
        "screens, recommend back or wait.\n\n"
        "Mission type: %s\n"
        "Mission goal: %s\n"
        "Mission targets: %s\n"
        "Mission success criteria: %s\n\n"
        "Learned memory:\n%s\n\n"
        "Recent actions and feedback:\n%s\n\n"
        "Current mission draft:\n%s\n\n"
        "Return only one JSON object. Do not include Markdown fences or explanations. "
        "Use exactly these top-level fields, even when a field has no content:\n"
        "{\n"
        '  "screen_summary": "short visual summary",\n'
        '  "state": "stable_state_name",\n'
        '  "action": {"type": "wait", "seconds": 1},\n'
        '  "reason": "why this safe action is useful",\n'
        '  "new_findings": [],\n'
        '  "screenshot_tags": [],\n'
        '  "risks": [],\n'
        '  "progress": {"level_label": "", "target_counts": [], "terminal_state": ""}\n'
        "}"
    ) % (
        mission.type,
        mission.goal,
        json.dumps(mission.targets, ensure_ascii=False),
        json.dumps(mission.success_criteria, ensure_ascii=False),
        compact_text(memory_summary, 1200) or "(none)",
        json.dumps(compact_recent_actions(recent_actions), ensure_ascii=False),
        compact_text(mission_draft, MAX_MISSION_DRAFT_CHARS),
    )


def compact_recent_actions(recent_actions, limit=MAX_PROMPT_RECENT_ACTIONS):
    compacted = []
    for action in list(recent_actions or [])[-limit:]:
        compacted.append(
            {
                "step": action.get("step"),
                "screen": action.get("screen"),
                "action": action.get("action"),
                "result": action.get("result"),
                "reason": compact_text(action.get("reason", ""), 160),
                "feedback_result": action.get("feedback_result"),
                "feedback_evidence": compact_text(action.get("feedback_evidence", ""), 160),
                "before_counts": action.get("before_counts", []),
                "after_counts": action.get("after_counts", []),
                "progress_delta": action.get("progress_delta", 0),
                "next_strategy": action.get("next_strategy"),
                "recommended_actions": action.get("recommended_actions", []),
                "recovery_reason": compact_text(action.get("recovery_reason", ""), 160),
            }
        )
    return compacted


def compact_text(text, limit):
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def _decision_schema():
    return {
        "type": "object",
        "properties": {
            "screen_summary": {"type": "string"},
            "state": {"type": "string"},
            "action": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "screenshot",
                            "wait",
                            "back",
                            "tap",
                            "swipe",
                            "hold_drag_release",
                        ],
                    },
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "x1": {"type": "integer"},
                    "y1": {"type": "integer"},
                    "x2": {"type": "integer"},
                    "y2": {"type": "integer"},
                    "seconds": {"type": "number"},
                    "duration": {"type": "number"},
                    "hold_seconds": {"type": "number"},
                },
                "required": ["type"],
                "additionalProperties": False,
            },
            "reason": {"type": "string"},
            "new_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "claim": {"type": "string"},
                        "evidence": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                    "required": ["category", "claim", "evidence", "confidence"],
                    "additionalProperties": False,
                },
            },
            "screenshot_tags": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
            "progress": {
                "type": "object",
                "properties": {
                    "level_label": {"type": "string"},
                    "target_counts": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "terminal_state": {"type": "string"},
                },
                "required": ["level_label", "target_counts", "terminal_state"],
                "additionalProperties": False,
            },
        },
        "required": REQUIRED_DECISION_FIELDS,
        "additionalProperties": False,
    }
