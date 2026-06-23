# -*- coding: utf-8 -*-
"""Tests for cross-session profile learning helpers."""

import unittest

from game_reverse.profile_learning import merge_profile_payloads, summarize_profile_memory


class TestProfileLearning(unittest.TestCase):
    def test_merges_state_maps_without_losing_history(self):
        existing = {
            "version": 1,
            "states": {
                "state_home": {
                    "state_id": "state_home",
                    "label": "home",
                    "visit_count": 2,
                    "first_seen_step": 1,
                    "last_seen_step": 5,
                }
            },
            "transitions": [{"step": 1, "to_state_id": "state_home", "session_name": "old"}],
        }
        current = {
            "version": 1,
            "states": {
                "state_home": {
                    "state_id": "state_home",
                    "label": "home",
                    "visit_count": 3,
                    "first_seen_step": 1,
                    "last_seen_step": 7,
                },
                "state_level": {
                    "state_id": "state_level",
                    "label": "level",
                    "visit_count": 1,
                    "first_seen_step": 8,
                    "last_seen_step": 8,
                },
            },
            "transitions": [{"step": 8, "to_state_id": "state_level"}],
        }

        merged = merge_profile_payloads(
            existing_state_map=existing,
            current_state_map=current,
            existing_affordances={"version": 1, "states": {}},
            current_affordances={"version": 1, "states": {}},
            existing_skills={"version": 1, "skills": []},
            mined_skills=[],
            session_name="new-run",
        )

        state_map = merged["state_map"]
        self.assertEqual(state_map["states"]["state_home"]["visit_count"], 5)
        self.assertEqual(state_map["states"]["state_home"]["last_seen_step"], 7)
        self.assertIn("state_level", state_map["states"])
        self.assertEqual(state_map["transitions"][-1]["session_name"], "new-run")

    def test_merges_skills_by_name_and_keeps_higher_confidence(self):
        merged = merge_profile_payloads(
            existing_state_map={"version": 1, "states": {}, "transitions": []},
            current_state_map={"version": 1, "states": {}, "transitions": []},
            existing_affordances={"version": 1, "states": {}},
            current_affordances={"version": 1, "states": {}},
            existing_skills={
                "version": 1,
                "skills": [
                    {
                        "name": "aim_at_target",
                        "confidence": 0.6,
                        "run_count": 1,
                        "success_count": 1,
                        "failure_count": 0,
                        "steps": [{"type": "tap", "x": 1, "y": 2}],
                    }
                ],
            },
            mined_skills=[
                {
                    "name": "aim_at_target",
                    "confidence": 0.55,
                    "run_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "steps": [{"type": "hold_drag_release", "x1": 1, "y1": 2, "x2": 3, "y2": 4}],
                },
                {
                    "name": "close_popup",
                    "confidence": 0.55,
                    "run_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "steps": [{"type": "back"}],
                },
            ],
            session_name="new-run",
        )

        skills = {skill["name"]: skill for skill in merged["skills"]["skills"]}
        self.assertEqual(skills["aim_at_target"]["confidence"], 0.6)
        self.assertEqual(skills["aim_at_target"]["run_count"], 1)
        self.assertIn("close_popup", skills)

    def test_summarizes_recent_profile_memory_for_prompt(self):
        summary = summarize_profile_memory(
            {
                "goals": {"active_subgoal": "detect result state"},
                "skills": {
                    "skills": [
                        {"name": "aim_at_target", "confidence": 0.8, "success_signal": "counter_changed"}
                        ,
                        {
                            "name": "continuous_aim",
                            "type": "continuous_control",
                            "controller": "aim_fire",
                            "confidence": 0.7,
                            "success_signal": "target_collected",
                        },
                    ]
                },
                "recent_memory": [
                    {
                        "feedback_result": "no_visible_change",
                        "action": {"type": "tap"},
                        "state_id": "state_a",
                    },
                    {
                        "feedback_result": "counter_changed",
                        "action": {"type": "hold_drag_release"},
                        "state_id": "state_b",
                    },
                ],
            },
            max_lines=5,
        )

        self.assertIn("active_subgoal: detect result state", summary)
        self.assertIn("aim_at_target", summary)
        self.assertIn("continuous_control: continuous_aim", summary)
        self.assertIn("counter_changed", summary)
        self.assertLessEqual(len(summary.splitlines()), 5)


if __name__ == "__main__":
    unittest.main()
