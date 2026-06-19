# -*- coding: utf-8 -*-
"""Tests for read-only learned profile summaries."""

import json
import os
import tempfile
import unittest

from game_reverse.profile_view import load_profile_summary


class TestProfileView(unittest.TestCase):
    def test_loads_profile_summary_for_web_console(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_dir = os.path.join(tmpdir, "com.example.game")
            os.makedirs(profile_dir)
            self.write_json(
                profile_dir,
                "state_map.json",
                {
                    "version": 1,
                    "states": {
                        "state_old": {
                            "state_id": "state_old",
                            "label": "home",
                            "summary": "Home screen",
                            "last_seen_step": 1,
                            "visit_count": 1,
                            "screenshot_tags": ["home"],
                        },
                        "state_new": {
                            "state_id": "state_new",
                            "label": "gameplay",
                            "summary": "Gameplay screen",
                            "last_seen_step": 4,
                            "visit_count": 3,
                            "screenshot_tags": ["level"],
                        },
                    },
                    "transitions": [
                        {
                            "step": 2,
                            "from_state_id": "state_old",
                            "to_state_id": "state_new",
                            "classification": "entered_new_state",
                        }
                    ],
                },
            )
            self.write_json(
                profile_dir,
                "affordances.json",
                {
                    "version": 1,
                    "states": {
                        "state_new": [
                            {
                                "id": "aff_start",
                                "state_id": "state_new",
                                "label": "Start",
                                "confidence": 0.9,
                                "last_result": "level_started",
                                "status": "useful",
                                "bounds": [10, 20, 100, 80],
                                "supported_actions": ["tap"],
                            }
                        ]
                    },
                },
            )
            self.write_json(
                profile_dir,
                "skills.json",
                {
                    "version": 1,
                    "skills": [
                        {
                            "name": "start_level",
                            "confidence": 0.8,
                            "run_count": 2,
                            "success_count": 2,
                            "failure_count": 0,
                            "trigger": {"state_labels": ["state_new"]},
                        }
                    ],
                },
            )
            self.write_json(
                profile_dir,
                "safety_rules.json",
                {
                    "version": 1,
                    "sensitive_states": ["state_login"],
                    "interventions": [
                        {"step": 3, "state_id": "state_login", "reason": "login gate"}
                    ],
                },
            )
            self.write_json(
                profile_dir,
                "goals.json",
                {
                    "version": 1,
                    "main_goal": "Explore safely",
                    "active_subgoal": "interact with core task",
                    "completed_subgoals": ["stabilize launch state"],
                    "blocked_subgoals": [],
                    "next_candidates": ["detect result state"],
                },
            )
            with open(os.path.join(profile_dir, "memory.jsonl"), "w", encoding="utf-8") as memory_file:
                memory_file.write(json.dumps({"event": "step", "step": 1}, sort_keys=True) + "\n")
                memory_file.write(json.dumps({"event": "step", "step": 4}, sort_keys=True) + "\n")

            summary = load_profile_summary(tmpdir, "com.example.game")

        self.assertTrue(summary["exists"])
        self.assertEqual(summary["package_name"], "com.example.game")
        self.assertEqual(summary["current_state"]["state_id"], "state_new")
        self.assertEqual(summary["states"][0]["state_id"], "state_new")
        self.assertEqual(summary["transitions"][0]["classification"], "entered_new_state")
        self.assertEqual(summary["affordances"][0]["label"], "Start")
        self.assertEqual(summary["skills"][0]["name"], "start_level")
        self.assertEqual(summary["safety"]["interventions"][0]["reason"], "login gate")
        self.assertEqual(summary["goals"]["active_subgoal"], "interact with core task")
        self.assertEqual(summary["memory_summary"]["event_count"], 2)
        self.assertEqual(summary["recent_memory"][-1]["step"], 4)

    def test_missing_profile_returns_empty_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = load_profile_summary(tmpdir, "com.missing.game")

        self.assertFalse(summary["exists"])
        self.assertEqual(summary["current_state"], {})
        self.assertEqual(summary["affordances"], [])
        self.assertEqual(summary["skills"], [])
        self.assertEqual(summary["safety"]["sensitive_states"], [])

    def write_json(self, profile_dir, filename, payload):
        with open(os.path.join(profile_dir, filename), "w", encoding="utf-8") as json_file:
            json.dump(payload, json_file, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
