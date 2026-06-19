# -*- coding: utf-8 -*-
"""Mission draft updates and final report writing."""

import json
import os
from collections import Counter


def update_mission_draft(current_draft, step, decision):
    lines = [current_draft.rstrip(), "", "## Step %04d 新发现" % step]
    for finding in decision.get("new_findings", []):
        lines.append("- **%s**: %s" % (finding["category"], finding["claim"]))
        lines.append("  - 证据: %s" % finding["evidence"])
        lines.append("  - 置信度: %s" % finding["confidence"])
    if decision.get("risks"):
        lines.append("- 风险: %s" % "；".join(decision["risks"]))
    lines.append("")
    return "\n".join(lines)


def write_final_report(session_dir, mission_draft, mission, stop_reason):
    states = _load_state_counts(session_dir)
    goals = _load_goals(session_dir)
    title = _report_title(mission.type)
    sections = [
        "# %s" % title,
        "",
        "## Mission",
        "",
        "- 类型: %s" % mission.type,
        "- 目标: %s" % mission.goal,
        "- 关注对象: %s" % ("、".join(mission.targets) if mission.targets else "无指定目标"),
        "",
        "## 停止原因",
        "",
        stop_reason,
        "",
        "## 状态覆盖",
        "",
    ]
    for state, count in states.most_common():
        sections.append("- %s: %s 次" % (state, count))
    sections.extend(_goal_sections(goals))
    sections.extend(_mission_sections(mission.type))
    sections.extend(["", "## 任务草稿", "", mission_draft])

    with open(os.path.join(session_dir, "final_report.md"), "w", encoding="utf-8") as report_file:
        report_file.write("\n".join(sections))


def _load_state_counts(session_dir):
    observations_path = os.path.join(session_dir, "observations.jsonl")
    states = Counter()
    if os.path.exists(observations_path):
        with open(observations_path, "r", encoding="utf-8") as observations_file:
            for line in observations_file:
                if line.strip():
                    observation = json.loads(line)
                    states[observation.get("state", "unknown")] += 1
    return states


def _load_goals(session_dir):
    goals_path = os.path.join(session_dir, "goals.json")
    if not os.path.exists(goals_path):
        return {}
    with open(goals_path, "r", encoding="utf-8") as goals_file:
        return json.load(goals_file)


def _goal_sections(goals):
    if not goals:
        return []
    sections = [
        "",
        "## Goal Progress",
        "",
        "- Main goal: %s" % goals.get("main_goal", ""),
        "- Active subgoal: %s" % goals.get("active_subgoal", ""),
    ]
    completed = goals.get("completed_subgoals") or []
    if completed:
        sections.append("- Completed subgoals: %s" % ", ".join(completed))
    blocked = goals.get("blocked_subgoals") or []
    if blocked:
        sections.append("- Blocked subgoals:")
        for item in blocked:
            sections.append("  - %s: %s" % (item.get("subgoal", ""), item.get("reason", "")))
    next_candidates = goals.get("next_candidates") or []
    if next_candidates:
        sections.append("- Next candidates: %s" % ", ".join(next_candidates))
    return sections


def _report_title(mission_type):
    if mission_type == "feature_test":
        return "App/Game 功能测试阶段报告"
    if mission_type == "level_design_reverse":
        return "关卡设计逆推报告"
    return "App/Game 自由探索报告"


def _mission_sections(mission_type):
    if mission_type == "feature_test":
        return ["", "## 功能覆盖", "", "## 失败或卡住步骤", "", "## 可疑 Bug", ""]
    if mission_type == "level_design_reverse":
        return ["", "## 关卡入口与路径", "", "## 关卡列表结构", "", "## 奖励与解锁条件", "", "## 难度递进推测", ""]
    return ["", "## 功能地图", "", "## 可疑入口", "", "## 下一轮探索建议", ""]
