# -*- coding: utf-8 -*-
"""Tests for reusable skill library support."""

import unittest

from game_reverse.skill_library import SkillLibrary


class FakeExecutor:
    def __init__(self, fail_on=None):
        self.executed = []
        self.fail_on = fail_on

    def execute(self, action, screen_path):
        self.executed.append(action)
        if action["type"] == self.fail_on:
            raise RuntimeError("executor failed")
        return "executed"


class TestSkillLibrary(unittest.TestCase):
    def test_matches_high_confidence_skill_by_state_label(self):
        library = SkillLibrary(
            [
                {
                    "name": "start_level",
                    "trigger": {"state_labels": ["main_menu"]},
                    "steps": [{"type": "tap", "x": 100, "y": 200}],
                    "success_signal": "level_started",
                    "failure_signal": "no_visible_change",
                    "confidence": 0.8,
                    "run_count": 0,
                }
            ]
        )

        skill = library.best_match({"state": "main_menu", "state_labels": ["home"]})

        self.assertEqual(skill["name"], "start_level")

    def test_ignores_low_confidence_skill(self):
        library = SkillLibrary(
            [
                {
                    "name": "weak_skill",
                    "trigger": {"state_labels": ["main_menu"]},
                    "steps": [{"type": "tap", "x": 100, "y": 200}],
                    "confidence": 0.2,
                }
            ]
        )

        self.assertIsNone(library.best_match({"state": "main_menu"}))

    def test_replays_valid_steps_and_increases_confidence(self):
        library = SkillLibrary(
            [
                {
                    "name": "close_popup",
                    "trigger": {"state_labels": ["popup"]},
                    "steps": [{"type": "tap", "x": 50, "y": 60}, {"type": "wait", "seconds": 1}],
                    "confidence": 0.6,
                    "run_count": 0,
                }
            ]
        )
        skill = library.skills[0]
        executor = FakeExecutor()

        attempt = library.replay(
            skill,
            executor=executor,
            screen_path="screens/step_0001.png",
            screen_size=(1080, 1920),
            allowed_actions=["tap", "wait"],
        )

        self.assertTrue(attempt["success"])
        self.assertEqual([action["type"] for action in executor.executed], ["tap", "wait"])
        self.assertGreater(skill["confidence"], 0.6)
        self.assertEqual(skill["run_count"], 1)

    def test_replays_targeted_steps_as_resolved_actions(self):
        library = SkillLibrary(
            [
                {
                    "name": "tap_start",
                    "trigger": {"state_labels": ["main_menu"]},
                    "steps": [
                        {
                            "type": "tap_target",
                            "target": {"bounds": [100, 200, 220, 260]},
                            "target_ref": "start_button",
                        }
                    ],
                    "confidence": 0.8,
                }
            ]
        )
        skill = library.skills[0]
        executor = FakeExecutor()

        attempt = library.replay(
            skill,
            executor=executor,
            screen_path="screens/step_0001.png",
            screen_size=(1080, 1920),
            allowed_actions=["tap_target"],
        )

        self.assertTrue(attempt["success"])
        self.assertEqual(executor.executed[0]["type"], "tap")
        self.assertEqual(executor.executed[0]["x"], 160)
        self.assertEqual(executor.executed[0]["target_ref"], "start_button")

    def test_failed_replay_decreases_confidence(self):
        library = SkillLibrary(
            [
                {
                    "name": "bad_skill",
                    "trigger": {"state_labels": ["main_menu"]},
                    "steps": [{"type": "tap", "x": 50, "y": 60}],
                    "confidence": 0.7,
                    "run_count": 0,
                }
            ]
        )
        skill = library.skills[0]

        attempt = library.replay(
            skill,
            executor=FakeExecutor(fail_on="tap"),
            screen_path="screens/step_0001.png",
            screen_size=(1080, 1920),
            allowed_actions=["tap"],
        )

        self.assertFalse(attempt["success"])
        self.assertLess(skill["confidence"], 0.7)
        self.assertEqual(skill["failure_count"], 1)

    def test_mines_skill_candidate_from_successful_trace(self):
        library = SkillLibrary()

        candidates = library.mine_candidates(
            [
                {
                    "state_id": "state_home",
                    "state": "main_menu",
                    "action": {"type": "tap", "x": 100, "y": 200},
                    "feedback_result": "level_started",
                }
            ]
        )

        self.assertEqual(candidates[0]["name"], "skill_from_main_menu_to_level_started")
        self.assertEqual(candidates[0]["steps"], [{"type": "tap", "x": 100, "y": 200}])

    def test_mines_continuous_control_skill_from_successful_aim_fire(self):
        library = SkillLibrary()

        candidates = library.mine_candidates(
            [
                {
                    "state_id": "state_level",
                    "state": "level_gameplay",
                    "action": {
                        "type": "aim_fire",
                        "control": {"x": 450, "y": 1175, "role": "fire_button"},
                        "cursor": {"x": 500, "y": 800, "role": "crosshair"},
                        "target": {"x": 420, "y": 760, "role": "collectible", "label": "milk carton"},
                    },
                    "feedback_result": "counter_changed",
                    "control_feedback": "target_collected",
                }
            ]
        )

        self.assertEqual(candidates[0]["type"], "continuous_control")
        self.assertEqual(candidates[0]["controller"], "aim_fire")
        self.assertEqual(candidates[0]["parameters"]["target_role"], "collectible")
        self.assertEqual(candidates[0]["success_signal"], "target_collected")
        self.assertEqual(candidates[0]["steps"], [])


if __name__ == "__main__":
    unittest.main()
