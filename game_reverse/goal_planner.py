# -*- coding: utf-8 -*-
"""Goal lifecycle planning for game_reverse runs."""

from copy import deepcopy


GOAL_SCHEMA_VERSION = 1
DEFAULT_GOAL_LADDER = [
    "stabilize launch state",
    "dismiss safe popups",
    "identify main navigation",
    "enter primary flow",
    "interact with core task",
    "detect result state",
    "continue safe progression",
]


class GoalPlanner:
    def __init__(self, mission, existing=None):
        existing = existing or {}
        self.main_goal = existing.get("main_goal") or getattr(mission, "goal", "") or "Explore safely"
        self.completed_subgoals = list(existing.get("completed_subgoals", []))
        self.blocked_subgoals = list(existing.get("blocked_subgoals", []))
        self.goal_ladder = list(existing.get("goal_ladder", DEFAULT_GOAL_LADDER))
        self.active_subgoal = existing.get("active_subgoal") or self._next_unfinished_subgoal()
        self.next_candidates = self._next_candidates()
        self.last_event = {
            "event": "goal_initialized",
            "active_subgoal": self.active_subgoal,
            "reason": "",
        }

    def update(self, observation, action_record, feedback):
        result = (feedback or {}).get("result", "")
        if result == "sensitive_screen":
            event = self._block_active_subgoal((feedback or {}).get("evidence", "sensitive screen"))
            self.active_subgoal = "recover to safe screen"
            self.next_candidates = ["back", "wait", self._next_unfinished_subgoal()]
            self.last_event = event
            return event
        if result in ("level_failed", "executor_error"):
            event = self._block_active_subgoal((feedback or {}).get("evidence", result))
            self.active_subgoal = "recover from failure"
            self.next_candidates = ["back", "retry alternate path", self._next_unfinished_subgoal()]
            self.last_event = event
            return event
        if result in ("level_started", "level_completed", "popup_closed", "state_changed", "entered_new_state"):
            event = self._complete_active_subgoal(result)
            self.active_subgoal = self._next_unfinished_subgoal()
            self.next_candidates = self._next_candidates()
            self.last_event = event
            return event

        event = {
            "event": "subgoal_progress",
            "active_subgoal": self.active_subgoal,
            "feedback_result": result,
            "reason": "",
        }
        self.next_candidates = self._next_candidates()
        self.last_event = event
        return event

    def replan(self, proposal):
        proposal = proposal or {}
        active_subgoal = proposal.get("active_subgoal")
        if active_subgoal:
            self.active_subgoal = active_subgoal

        if "goal_ladder" in proposal and isinstance(proposal.get("goal_ladder"), list):
            self.goal_ladder = [item for item in proposal["goal_ladder"] if item]
        self._merge_completed(proposal.get("completed_subgoals", []))
        self._merge_blocked(proposal.get("blocked_subgoals", []))

        next_candidates = proposal.get("next_candidates")
        if isinstance(next_candidates, list):
            self.next_candidates = [item for item in next_candidates if item]
        else:
            self.next_candidates = self._next_candidates()

        event = {
            "event": "goal_replanned",
            "active_subgoal": self.active_subgoal,
            "reason": proposal.get("reason", ""),
            "next_candidates": list(self.next_candidates),
        }
        self.last_event = event
        return event

    def to_goals(self):
        return {
            "version": GOAL_SCHEMA_VERSION,
            "main_goal": self.main_goal,
            "active_subgoal": self.active_subgoal,
            "completed_subgoals": list(self.completed_subgoals),
            "blocked_subgoals": deepcopy(self.blocked_subgoals),
            "next_candidates": list(self.next_candidates),
            "goal_ladder": list(self.goal_ladder),
        }

    def _complete_active_subgoal(self, reason):
        if self.active_subgoal and self.active_subgoal not in self.completed_subgoals:
            self.completed_subgoals.append(self.active_subgoal)
        return {
            "event": "subgoal_completed",
            "active_subgoal": self.active_subgoal,
            "feedback_result": reason,
            "reason": reason,
        }

    def _block_active_subgoal(self, reason):
        blocked = {
            "subgoal": self.active_subgoal,
            "reason": reason,
        }
        self.blocked_subgoals.append(blocked)
        return {
            "event": "subgoal_blocked",
            "active_subgoal": self.active_subgoal,
            "reason": reason,
        }

    def _next_unfinished_subgoal(self):
        completed = set(self.completed_subgoals)
        blocked = {item.get("subgoal") for item in self.blocked_subgoals}
        for subgoal in self.goal_ladder:
            if subgoal not in completed and subgoal not in blocked:
                return subgoal
        return "complete run summary"

    def _next_candidates(self):
        candidates = []
        for subgoal in self.goal_ladder:
            if subgoal != self.active_subgoal and subgoal not in self.completed_subgoals:
                candidates.append(subgoal)
            if len(candidates) >= 3:
                break
        return candidates

    def _merge_completed(self, completed_subgoals):
        for subgoal in completed_subgoals or []:
            if subgoal and subgoal not in self.completed_subgoals:
                self.completed_subgoals.append(subgoal)

    def _merge_blocked(self, blocked_subgoals):
        existing = {
            (item.get("subgoal"), item.get("reason", ""))
            for item in self.blocked_subgoals
            if isinstance(item, dict)
        }
        for item in blocked_subgoals or []:
            if isinstance(item, str):
                blocked = {"subgoal": item, "reason": ""}
            elif isinstance(item, dict):
                blocked = {
                    "subgoal": item.get("subgoal", ""),
                    "reason": item.get("reason", ""),
                }
            else:
                continue
            key = (blocked.get("subgoal"), blocked.get("reason", ""))
            if blocked.get("subgoal") and key not in existing:
                self.blocked_subgoals.append(blocked)
                existing.add(key)
