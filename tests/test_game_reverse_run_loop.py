# -*- coding: utf-8 -*-
"""Tests for the mission-driven game_reverse run loop."""

import os
import tempfile
import unittest

from game_reverse.config import GameReverseConfig
from game_reverse.mission import Mission
from game_reverse.run_loop import run_loop


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


class FakeDecider:
    def decide(self, screen_path, mission, recent_actions, mission_draft):
        return {
            "screen_summary": "主界面",
            "state": "main_menu",
            "action": {"type": "wait", "seconds": 1},
            "reason": "等待观察",
            "new_findings": [
                {
                    "category": "主界面",
                    "claim": "发现主界面",
                    "evidence": screen_path,
                    "confidence": "high",
                }
            ],
            "screenshot_tags": ["主界面"],
            "risks": [],
        }


class TestRunLoop(unittest.TestCase):
    def test_runs_fixed_number_of_steps_with_mission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=2,
                output_root=tmpdir,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="feature_test", goal="测试任务", targets=["任务"]),
            )
            executor = FakeExecutor()

            session_dir = run_loop(
                config,
                executor=executor,
                decider=FakeDecider(),
                session_name="test-session",
            )

            self.assertTrue(os.path.exists(os.path.join(session_dir, "actions.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "observations.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "mission_draft.md")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "final_report.md")))
            self.assertEqual(len([call for call in executor.executed if call[0]["type"] == "wait"]), 2)

            with open(os.path.join(session_dir, "final_report.md"), "r", encoding="utf-8") as report_file:
                report = report_file.read()

        self.assertIn("功能测试阶段报告", report)


if __name__ == "__main__":
    unittest.main()
