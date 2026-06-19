# -*- coding: utf-8 -*-
"""Tests for the lightweight game_reverse step runner."""

import json
import os
import tempfile
import unittest

from game_reverse.config import GameReverseConfig
from game_reverse.lightweight_runner import run_lightweight_loop
from game_reverse.mission import Mission


class FakeExecutor:
    def __init__(self):
        self.executed = []

    def connect(self, device_uri):
        self.device_uri = device_uri

    def start_app(self, package_name):
        self.package_name = package_name

    def execute(self, action, screen_path):
        self.executed.append((action, screen_path))
        if action["type"] == "screenshot":
            with open(screen_path, "wb") as screen_file:
                screen_file.write(b"fake png")
        return "executed"


class JsonActionDecider:
    def __init__(self):
        self.calls = []

    def decide_action(self, step_input):
        self.calls.append(step_input)
        return {
            "screen_summary": "screen %s" % step_input["step"],
            "state": "stable",
            "action": {"type": "wait", "seconds": 0},
            "reason": "single JSON action",
            "new_findings": ["finding %s" % step_input["step"]],
            "screenshot_tags": ["screen"],
            "risks": [],
        }


class TestLightweightRunner(unittest.TestCase):
    def test_lightweight_runner_writes_artifacts_for_ten_steps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=10,
                output_root=tmpdir,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="explore", targets=["target"]),
            )
            executor = FakeExecutor()
            decider = JsonActionDecider()

            session_dir = run_lightweight_loop(
                config,
                executor=executor,
                decider=decider,
                session_name="lightweight-session",
            )

            self.assertTrue(os.path.exists(os.path.join(session_dir, "actions.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "observations.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "final_report.md")))
            self.assertEqual(len(os.listdir(os.path.join(session_dir, "screens"))), 10)
            self.assertEqual(len([call for call in executor.executed if call[0]["type"] == "wait"]), 10)
            self.assertEqual(len(decider.calls), 10)
            self.assertNotIn("mission_draft", decider.calls[0])
            self.assertEqual(decider.calls[-1]["recent_actions"][-1]["step"], 9)

            with open(os.path.join(session_dir, "actions.jsonl"), encoding="utf-8") as action_file:
                actions = [json.loads(line) for line in action_file if line.strip()]
            with open(os.path.join(session_dir, "observations.jsonl"), encoding="utf-8") as observation_file:
                observations = [json.loads(line) for line in observation_file if line.strip()]

        self.assertEqual(len(actions), 10)
        self.assertEqual(len(observations), 10)
        self.assertEqual(actions[0]["action"], {"type": "wait", "seconds": 0})
        self.assertEqual(observations[0]["state"], "stable")


if __name__ == "__main__":
    unittest.main()
