# -*- coding: utf-8 -*-
"""Configuration loading for game_reverse."""

import json
from dataclasses import dataclass, field

from game_reverse.mission import Mission, parse_mission

DEFAULT_ALLOWED_ACTIONS = ["screenshot", "wait", "back"]


@dataclass
class GameReverseConfig:
    device_uri: str = None
    package_name: str = None
    max_steps: int = 50
    mission: Mission = field(default_factory=Mission)
    model: str = "claude-opus-4-8"
    output_root: str = "game_reverse/outputs/sessions"
    allowed_actions: list = field(default_factory=lambda: list(DEFAULT_ALLOWED_ACTIONS))
    recent_steps: int = 5
    llm_retry_count: int = 1
    consecutive_failure_limit: int = 3


def load_config(path):
    with open(path, "r", encoding="utf-8") as config_file:
        raw = json.load(config_file)

    package_name = raw.get("package_name")
    if not package_name:
        raise ValueError("package_name is required")

    max_steps = raw.get("max_steps", 50)
    if not isinstance(max_steps, int) or max_steps <= 0:
        raise ValueError("max_steps must be a positive int")

    return GameReverseConfig(
        device_uri=raw.get("device_uri", "Android:///"),
        package_name=package_name,
        max_steps=max_steps,
        mission=parse_mission(raw.get("mission")),
        model=raw.get("model", "claude-opus-4-8"),
        output_root=raw.get("output_root", "game_reverse/outputs/sessions"),
        allowed_actions=list(raw.get("allowed_actions", DEFAULT_ALLOWED_ACTIONS)),
        recent_steps=raw.get("recent_steps", 5),
        llm_retry_count=raw.get("llm_retry_count", 1),
        consecutive_failure_limit=raw.get("consecutive_failure_limit", 3),
    )
