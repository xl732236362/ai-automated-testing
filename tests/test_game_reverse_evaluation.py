# -*- coding: utf-8 -*-
"""Tests for cross-app evaluation metrics and reports."""

import json
import os
import tempfile
import unittest

from game_reverse.evaluation import (
    collect_session_metrics,
    compare_sessions,
    default_benchmark_scenarios,
    main,
    write_comparison_json,
    write_comparison_report,
)


class TestGameReverseEvaluation(unittest.TestCase):
    def test_default_benchmark_scenarios_cover_target_categories(self):
        scenarios = default_benchmark_scenarios()

        scenario_ids = [item["id"] for item in scenarios]

        self.assertIn("ordinary_app", scenario_ids)
        self.assertIn("menu_heavy_game", scenario_ids)
        self.assertIn("pure_render_game", scenario_ids)

    def test_collects_session_metrics_from_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = self.create_session(
                tmpdir,
                "menu-run",
                states=["state_home", "state_level"],
                transitions=[
                    {"step": 1, "classification": "entered_new_state"},
                    {"step": 2, "classification": "no_change"},
                    {"step": 3, "classification": "state_changed"},
                ],
                actions=[
                    {
                        "step": 1,
                        "action_source": "llm",
                        "feedback_result": "entered_new_state",
                        "safety_label": "safe",
                    },
                    {
                        "step": 2,
                        "action_source": "skill",
                        "feedback_result": "no_visible_change",
                        "safety_label": "safe",
                    },
                    {
                        "step": 3,
                        "action_source": "llm",
                        "feedback_result": "sensitive_screen",
                        "safety_label": "sensitive",
                    },
                ],
                skill_attempts=[
                    {"skill_name": "start", "success": True},
                    {"skill_name": "bad", "success": False},
                ],
                completed_subgoals=["stabilize launch state", "identify main navigation"],
                observations=[{"step": 1}, {"step": 2}, {"step": 3}],
            )

            metrics = collect_session_metrics(session_dir, scenario_id="menu_heavy_game")

        self.assertEqual(metrics["scenario_id"], "menu_heavy_game")
        self.assertEqual(metrics["session_id"], "menu-run")
        self.assertEqual(metrics["states_discovered"], 2)
        self.assertEqual(metrics["transitions_discovered"], 3)
        self.assertEqual(metrics["useful_transitions"], 2)
        self.assertAlmostEqual(metrics["visible_effect_rate"], 1 / 3)
        self.assertEqual(metrics["repeated_no_change_count"], 1)
        self.assertEqual(metrics["unsafe_screen_avoidance_count"], 1)
        self.assertEqual(metrics["skills_attempted"], 2)
        self.assertEqual(metrics["skills_succeeded"], 1)
        self.assertEqual(metrics["skills_failed"], 1)
        self.assertAlmostEqual(metrics["skill_reuse_rate"], 1 / 3)
        self.assertEqual(metrics["subgoals_completed"], 2)
        self.assertEqual(metrics["progress_depth"], 3)
        self.assertEqual(metrics["llm_calls_per_useful_transition"], 1.0)

    def test_compares_sessions_and_flags_regressions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            strong = self.create_session(
                tmpdir,
                "20260619-001",
                states=["a", "b", "c"],
                transitions=[
                    {"step": 1, "classification": "entered_new_state"},
                    {"step": 2, "classification": "state_changed"},
                ],
                actions=[
                    {"step": 1, "action_source": "llm", "feedback_result": "entered_new_state"},
                    {"step": 2, "action_source": "skill", "feedback_result": "state_changed"},
                ],
                completed_subgoals=["one", "two"],
                observations=[{"step": 1}, {"step": 2}],
            )
            weak = self.create_session(
                tmpdir,
                "20260619-002",
                states=["a"],
                transitions=[{"step": 1, "classification": "no_change"}],
                actions=[{"step": 1, "action_source": "llm", "feedback_result": "no_visible_change"}],
                completed_subgoals=[],
                observations=[{"step": 1}],
            )

            comparison = compare_sessions([strong, weak], scenario_id="pure_render_game")

        self.assertEqual(comparison["scenario_id"], "pure_render_game")
        self.assertEqual(len(comparison["runs"]), 2)
        self.assertTrue(comparison["regressions"])
        self.assertEqual(comparison["regressions"][0]["metric"], "states_discovered")

    def test_writes_markdown_and_json_comparison_reports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = self.create_session(
                tmpdir,
                "ordinary-run",
                states=["home", "settings"],
                transitions=[{"step": 1, "classification": "entered_new_state"}],
                actions=[{"step": 1, "action_source": "llm", "feedback_result": "entered_new_state"}],
                skill_attempts=[],
                completed_subgoals=["stabilize launch state"],
                observations=[{"step": 1}],
            )
            comparison = compare_sessions([session_dir], scenario_id="ordinary_app")
            markdown_path = os.path.join(tmpdir, "comparison.md")
            json_path = os.path.join(tmpdir, "comparison.json")

            write_comparison_report(comparison, markdown_path)
            write_comparison_json(comparison, json_path)

            markdown = self.read_text(markdown_path)
            with open(json_path, encoding="utf-8") as json_file:
                payload = json.load(json_file)

        self.assertIn("Cross-App Evaluation", markdown)
        self.assertIn("ordinary_app", markdown)
        self.assertIn("states discovered", markdown)
        self.assertIn("unsafe screens avoided", markdown)
        self.assertEqual(payload["scenario_id"], "ordinary_app")

    def test_cli_writes_requested_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = self.create_session(
                tmpdir,
                "cli-run",
                states=["home"],
                transitions=[{"step": 1, "classification": "entered_new_state"}],
                actions=[{"step": 1, "action_source": "llm", "feedback_result": "entered_new_state"}],
                observations=[{"step": 1}],
            )
            json_path = os.path.join(tmpdir, "out.json")
            markdown_path = os.path.join(tmpdir, "out.md")

            exit_code = main(
                [
                    "--scenario",
                    "menu_heavy_game",
                    "--session",
                    session_dir,
                    "--json-output",
                    json_path,
                    "--markdown-output",
                    markdown_path,
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(json_path))
            self.assertTrue(os.path.exists(markdown_path))

    def create_session(
        self,
        root,
        name,
        states,
        transitions,
        actions,
        skill_attempts=None,
        completed_subgoals=None,
        observations=None,
    ):
        session_dir = os.path.join(root, name)
        os.makedirs(session_dir)
        state_payload = {
            "version": 1,
            "states": {
                state_id: {
                    "state_id": state_id,
                    "label": state_id,
                    "last_seen_step": index + 1,
                    "visit_count": 1,
                }
                for index, state_id in enumerate(states)
            },
            "transitions": transitions,
        }
        self.write_json(session_dir, "state_map.json", state_payload)
        self.write_json(
            session_dir,
            "goals.json",
            {
                "version": 1,
                "completed_subgoals": completed_subgoals or [],
            },
        )
        self.write_jsonl(session_dir, "actions.jsonl", actions)
        self.write_jsonl(session_dir, "skill_attempts.jsonl", skill_attempts or [])
        self.write_jsonl(session_dir, "observations.jsonl", observations or [])
        return session_dir

    def write_json(self, session_dir, filename, payload):
        with open(os.path.join(session_dir, filename), "w", encoding="utf-8") as json_file:
            json.dump(payload, json_file, ensure_ascii=False, sort_keys=True)

    def write_jsonl(self, session_dir, filename, records):
        with open(os.path.join(session_dir, filename), "w", encoding="utf-8") as jsonl_file:
            for record in records:
                jsonl_file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def read_text(self, path):
        with open(path, encoding="utf-8") as text_file:
            return text_file.read()


if __name__ == "__main__":
    unittest.main()
