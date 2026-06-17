# -*- coding: utf-8 -*-
"""Mission definitions for game_reverse."""

from dataclasses import dataclass, field
from typing import List

MISSION_TYPES = {"free_explore", "feature_test", "level_design_reverse"}
DEFAULT_GOAL = "自由探索 App/Game 并总结界面与功能"


@dataclass
class Mission:
    type: str = "free_explore"
    goal: str = DEFAULT_GOAL
    targets: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)


def parse_mission(raw):
    if raw is None:
        return Mission()
    if not isinstance(raw, dict):
        raise ValueError("mission must be an object")

    mission_type = raw.get("type", "free_explore")
    if mission_type not in MISSION_TYPES:
        raise ValueError("mission.type must be one of: %s" % ", ".join(sorted(MISSION_TYPES)))

    goal = raw.get("goal")
    if not goal:
        raise ValueError("mission.goal is required")

    targets = raw.get("targets", [])
    if not isinstance(targets, list):
        raise ValueError("mission.targets must be a list")

    success_criteria = raw.get("success_criteria", [])
    if not isinstance(success_criteria, list):
        raise ValueError("mission.success_criteria must be a list")

    return Mission(
        type=mission_type,
        goal=goal,
        targets=list(targets),
        success_criteria=list(success_criteria),
    )
