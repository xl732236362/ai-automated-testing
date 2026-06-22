# -*- coding: utf-8 -*-
"""Tests for goal lifecycle planning."""

import unittest

from game_reverse.goal_planner import GoalPlanner
from game_reverse.mission import Mission


class TestGoalPlanner(unittest.TestCase):
    def test_initializes_goal_stack_from_mission(self):
        planner = GoalPlanner(Mission(type="free_explore", goal="Explore app", targets=["home"]))
        goals = planner.to_goals()

        self.assertEqual(goals["main_goal"], "Explore app")
        self.assertEqual(goals["active_subgoal"], "stabilize launch state")
        self.assertIn("enter primary flow", goals["next_candidates"])

    def test_completes_active_subgoal_and_advances(self):
        planner = GoalPlanner(Mission(type="free_explore", goal="Explore app"))

        event = planner.update(
            observation={"state": "gameplay"},
            action_record={"action": {"type": "tap"}},
            feedback={"result": "level_started"},
        )
        goals = planner.to_goals()

        self.assertEqual(event["event"], "subgoal_completed")
        self.assertIn("stabilize launch state", goals["completed_subgoals"])
        self.assertNotEqual(goals["active_subgoal"], "stabilize launch state")

    def test_blocks_sensitive_subgoal_and_selects_recovery(self):
        planner = GoalPlanner(Mission(type="free_explore", goal="Explore app"))

        event = planner.update(
            observation={"state": "login"},
            action_record={"action": {"type": "tap"}},
            feedback={"result": "sensitive_screen", "evidence": "login required"},
        )
        goals = planner.to_goals()

        self.assertEqual(event["event"], "subgoal_blocked")
        self.assertEqual(goals["blocked_subgoals"][0]["reason"], "login required")
        self.assertEqual(goals["active_subgoal"], "recover to safe screen")

    def test_avoids_completed_subgoals_when_selecting_next(self):
        planner = GoalPlanner(
            Mission(type="free_explore", goal="Explore app"),
            existing={
                "completed_subgoals": [
                    "stabilize launch state",
                    "dismiss safe popups",
                ],
            },
        )

        self.assertEqual(planner.to_goals()["active_subgoal"], "identify main navigation")

    def test_replan_updates_active_subgoal_and_candidates(self):
        planner = GoalPlanner(Mission(type="free_explore", goal="Explore app"))

        event = planner.replan(
            {
                "active_subgoal": "try alternate navigation path",
                "next_candidates": ["swipe", "hold_drag_release"],
                "reason": "repeated no-change feedback",
            }
        )
        goals = planner.to_goals()

        self.assertEqual(event["event"], "goal_replanned")
        self.assertEqual(goals["active_subgoal"], "try alternate navigation path")
        self.assertEqual(goals["next_candidates"], ["swipe", "hold_drag_release"])
        self.assertEqual(planner.last_event["reason"], "repeated no-change feedback")


if __name__ == "__main__":
    unittest.main()
