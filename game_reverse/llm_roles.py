# -*- coding: utf-8 -*-
"""Role boundaries for LLM-assisted game_reverse exploration."""

from game_reverse.skill_library import SkillLibrary


class StateAnalyzer:
    """Extract observation-like state fields through the configured decider."""

    def __init__(self, decider):
        self.decider = decider

    def analyze(self, screen_path, mission, recent_actions=None, mission_draft=""):
        decision = self.decider.decide(screen_path, mission, recent_actions or [], mission_draft or "")
        return {
            "screen_summary": decision.get("screen_summary", ""),
            "state": decision.get("state", "unknown"),
            "findings": decision.get("new_findings", []),
            "screenshot_tags": decision.get("screenshot_tags", []),
            "risks": decision.get("risks", []),
            "ocr": decision.get("ocr", []),
            "ui_nodes": decision.get("ui_nodes", []),
            "visual_regions": decision.get("visual_regions", []),
            "proposed_regions": decision.get("proposed_regions", []),
        }


class ActionProposer:
    """Request the next safe action proposal through the configured decider."""

    def __init__(self, decider):
        self.decider = decider

    def propose(self, screen_path, mission, recent_actions=None, mission_draft=""):
        return self.decider.decide(screen_path, mission, recent_actions or [], mission_draft or "")


class RuleMiner:
    """Build deterministic rule summaries from feedback traces."""

    def mine(self, feedback_records):
        feedback_counts = {}
        action_counts = {}
        for record in feedback_records or []:
            feedback_result = record.get("feedback_result") or record.get("result") or "unknown"
            feedback_counts[feedback_result] = feedback_counts.get(feedback_result, 0) + 1
            action_type = (record.get("action") or {}).get("type")
            if action_type:
                action_counts[action_type] = action_counts.get(action_type, 0) + 1

        recommendations = []
        if feedback_counts.get("no_visible_change", 0) >= 2:
            recommendations.append("avoid repeating no-change actions")
        if feedback_counts.get("sensitive_screen", 0):
            recommendations.append("prefer back or wait on sensitive screens")
        if feedback_counts.get("level_failed", 0):
            recommendations.append("recover before retrying failed flows")

        return {
            "version": 1,
            "feedback_counts": feedback_counts,
            "action_counts": action_counts,
            "recommendations": recommendations,
        }


class SkillMiner:
    """Delegate reusable skill extraction to SkillLibrary."""

    def __init__(self, skill_library=None):
        self.skill_library = skill_library or SkillLibrary()

    def mine(self, action_records):
        return self.skill_library.mine_candidates(action_records)


class GoalReplanner:
    """Apply a role-produced plan update to GoalPlanner."""

    def replan(self, goal_planner, proposal):
        return goal_planner.replan(proposal)
