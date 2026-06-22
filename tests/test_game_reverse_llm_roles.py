# -*- coding: utf-8 -*-
"""Tests for explorer LLM role boundaries."""

import unittest

from game_reverse.llm_roles import ActionProposer, RuleMiner, SkillMiner, StateAnalyzer
from game_reverse.mission import Mission


class FakeDecider:
    def __init__(self):
        self.calls = []

    def decide(self, screen_path, mission, recent_actions, mission_draft):
        self.calls.append(
            {
                "screen_path": screen_path,
                "mission": mission,
                "recent_actions": recent_actions,
                "mission_draft": mission_draft,
            }
        )
        return {
            "screen_summary": "main menu",
            "state": "main_menu",
            "action": {"type": "tap_target", "target": {"bounds": [100, 200, 220, 260]}},
            "reason": "start candidate",
            "new_findings": [{"claim": "start is visible"}],
            "screenshot_tags": ["home"],
            "risks": [],
            "ocr": [{"text": "Start", "bounds": [100, 200, 220, 260]}],
        }


class TestLlmRoles(unittest.TestCase):
    def test_state_analyzer_delegates_to_decider_and_returns_observation_fields(self):
        decider = FakeDecider()
        analyzer = StateAnalyzer(decider)
        mission = Mission(type="free_explore", goal="Explore")

        observation = analyzer.analyze("screen.png", mission, recent_actions=[{"step": 1}], mission_draft="draft")

        self.assertEqual(observation["screen_summary"], "main menu")
        self.assertEqual(observation["state"], "main_menu")
        self.assertEqual(observation["findings"], [{"claim": "start is visible"}])
        self.assertEqual(observation["ocr"][0]["text"], "Start")
        self.assertEqual(decider.calls[0]["mission_draft"], "draft")

    def test_action_proposer_delegates_to_decider_and_preserves_action(self):
        decider = FakeDecider()
        proposer = ActionProposer(decider)

        proposal = proposer.propose(
            "screen.png",
            Mission(type="free_explore", goal="Explore"),
            recent_actions=[],
            mission_draft="",
        )

        self.assertEqual(proposal["action"]["type"], "tap_target")
        self.assertEqual(proposal["reason"], "start candidate")

    def test_rule_miner_summarizes_feedback_counts(self):
        rules = RuleMiner().mine(
            [
                {"feedback_result": "no_visible_change", "action": {"type": "tap"}},
                {"feedback_result": "no_visible_change", "action": {"type": "swipe"}},
                {"feedback_result": "entered_new_state", "action": {"type": "tap"}},
            ]
        )

        self.assertEqual(rules["version"], 1)
        self.assertEqual(rules["feedback_counts"]["no_visible_change"], 2)
        self.assertIn("avoid repeating no-change actions", rules["recommendations"])

    def test_skill_miner_delegates_to_skill_library_candidates(self):
        skills = SkillMiner().mine(
            [
                {
                    "state": "main_menu",
                    "action": {"type": "tap", "x": 100, "y": 200},
                    "feedback_result": "entered_new_state",
                }
            ]
        )

        self.assertEqual(skills[0]["name"], "skill_from_main_menu_to_entered_new_state")
        self.assertEqual(skills[0]["steps"][0]["type"], "tap")


if __name__ == "__main__":
    unittest.main()
