# -*- coding: utf-8 -*-
"""Tests for Claude decision parsing."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from game_reverse.llm_decider import (
    _build_decision_prompt,
    _create_anthropic_client,
    _decision_schema,
    parse_decision,
)
from game_reverse.mission import Mission


class TestLLMDecider(unittest.TestCase):
    def test_parses_valid_decision(self):
        decision = parse_decision(
            """{
              "screen_summary": "main screen",
              "state": "main_menu",
              "action": {"type": "wait", "seconds": 1},
              "reason": "瑙傚療鐣岄潰",
              "new_findings": [],
              "screenshot_tags": [],
              "risks": []
            }"""
        )

        self.assertEqual(decision["state"], "main_menu")
        self.assertEqual(decision["action"]["type"], "wait")

    def test_parses_json_wrapped_in_markdown(self):
        decision = parse_decision(
            """```json
            {
              "screen_summary": "main screen",
              "state": "main_menu",
              "action": {"type": "wait", "seconds": 1},
              "reason": "observe",
              "new_findings": [],
              "screenshot_tags": [],
              "risks": []
            }
            ```"""
        )

        self.assertEqual(decision["state"], "main_menu")
        self.assertEqual(decision["action"]["type"], "wait")

    def test_fills_non_action_fields_for_gpt_pool_responses(self):
        decision = parse_decision('{"action": {"type": "wait", "seconds": 1}, "reason": "observe"}')

        self.assertEqual(decision["screen_summary"], "")
        self.assertEqual(decision["state"], "unknown")
        self.assertEqual(decision["new_findings"], [])
        self.assertEqual(decision["screenshot_tags"], [])
        self.assertEqual(decision["risks"], [])

    def test_normalizes_string_findings_from_gpt_pool_responses(self):
        decision = parse_decision(
            """{
              "action": {"type": "wait", "seconds": 1},
              "new_findings": ["Current stage is Level 5."]
            }"""
        )

        self.assertEqual(
            decision["new_findings"],
            [
                {
                    "category": "finding",
                    "claim": "Current stage is Level 5.",
                    "evidence": "",
                    "confidence": "medium",
                }
            ],
        )

    def test_rejects_missing_action(self):
        with self.assertRaisesRegex(ValueError, "action"):
            parse_decision('{"screen_summary": "main screen", "state": "main_menu"}')

    def test_invalid_json_error_includes_response_preview(self):
        with self.assertRaisesRegex(ValueError, "not json"):
            parse_decision("not json")

    def test_create_client_uses_anthropic_environment_variables(self):
        fake_anthropic = mock.Mock()
        with mock.patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "env-key",
                "ANTHROPIC_BASE_URL": "https://proxy.example/v1",
            },
            clear=False,
        ), mock.patch.dict(sys.modules, {"anthropic": fake_anthropic}):
            _create_anthropic_client()

        fake_anthropic.Anthropic.assert_called_once_with(
            api_key="env-key",
            base_url="https://proxy.example/v1",
        )

    def test_create_client_loads_project_dotenv_without_overriding_existing_env(self):
        fake_anthropic = mock.Mock()
        dotenv_path = Path.cwd() / ".env"
        old_content = dotenv_path.read_text(encoding="utf-8") if dotenv_path.exists() else None
        dotenv_path.write_text(
            "ANTHROPIC_API_KEY=dotenv-key\n"
            "ANTHROPIC_BASE_URL=https://dotenv-proxy.example/v1\n",
            encoding="utf-8",
        )
        self.addCleanup(self._restore_file, dotenv_path, old_content)

        with mock.patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "env-key"},
            clear=True,
        ), mock.patch.dict(sys.modules, {"anthropic": fake_anthropic}):
            _create_anthropic_client()

        fake_anthropic.Anthropic.assert_called_once_with(
            api_key="env-key",
            base_url="https://dotenv-proxy.example/v1",
        )

    def test_decision_prompt_compacts_recent_actions_and_mission_draft(self):
        mission = Mission(type="free_explore", goal="Explore", targets=["target"])
        recent_actions = [
            {
                "step": index,
                "screen": "screens/step_%04d.png" % index,
                "action": {"type": "wait", "seconds": index},
                "reason": "reason %s" % index,
                "result": "executed",
                "large_unused_blob": "x" * 500,
            }
            for index in range(1, 12)
        ]
        mission_draft = "draft-start " + ("very long draft " * 500) + " draft-end"

        prompt = _build_decision_prompt(mission, recent_actions, mission_draft)

        self.assertNotIn("large_unused_blob", prompt)
        self.assertNotIn("step_0001", prompt)
        self.assertIn("step_0007", prompt)
        self.assertIn("step_0011", prompt)
        self.assertIn("draft-start", prompt)
        self.assertIn("[truncated]", prompt)
        self.assertNotIn("draft-end", prompt)
        self.assertLess(len(prompt), 7000)

    def test_decision_schema_allows_hold_drag_release(self):
        action_type = _decision_schema()["properties"]["action"]["properties"]["type"]

        self.assertIn("hold_drag_release", action_type["enum"])

    def test_decision_prompt_includes_feedback_strategy_from_recent_actions(self):
        mission = Mission(type="free_explore", goal="Explore", targets=["target"])
        recent_actions = [
            {
                "step": 1,
                "screen": "screens/step_0001.png",
                "action": {"type": "tap", "x": 100, "y": 200},
                "reason": "try target",
                "result": "executed",
                "feedback_result": "no_visible_change",
                "feedback_evidence": "screen summary unchanged",
                "next_strategy": "switch_gesture",
            }
        ]

        prompt = _build_decision_prompt(mission, recent_actions, "")

        self.assertIn("no_visible_change", prompt)
        self.assertIn("screen summary unchanged", prompt)
        self.assertIn("switch_gesture", prompt)

    def _restore_file(self, path, old_content):
        if old_content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(old_content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
