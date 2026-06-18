# -*- coding: utf-8 -*-
"""Tests for the static game explorer web console."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"


class TestWebConsoleStatic(unittest.TestCase):
    def test_static_files_exist(self):
        expected_files = [
            WEB_DIR / "index.html",
            WEB_DIR / "styles.css",
            WEB_DIR / "app.js",
            WEB_DIR / "data" / "sample-run.json",
        ]

        for path in expected_files:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), "%s should exist" % path)

    def test_index_wires_assets_and_sample_data(self):
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

        self.assertIn('lang="zh-CN"', html)
        self.assertIn('href="styles.css"', html)
        self.assertIn('rel="icon"', html)
        self.assertIn('src="app.js"', html)
        self.assertIn('data-sample-url="data/sample-run.json"', html)
        self.assertIn('id="event-log"', html)
        self.assertIn('id="session-list"', html)
        self.assertIn('id="device-uri-input"', html)
        self.assertIn('id="package-name-input"', html)
        self.assertIn('id="model-input"', html)
        self.assertIn('id="max-steps-input"', html)
        self.assertIn('id="mission-goal"', html)
        self.assertIn('id="allow-unsafe-actions-input"', html)
        self.assertIn("交互权限", html)
        self.assertIn("允许点击/滑动", html)
        self.assertIn("App/Game 探索控制台", html)

    def test_sample_run_json_has_required_shape(self):
        data = json.loads((WEB_DIR / "data" / "sample-run.json").read_text(encoding="utf-8"))

        self.assertEqual(data["config"]["device_uri"], "Android:///emulator-5554")
        self.assertEqual(data["config"]["package_name"], "com.example.game")
        self.assertIn(
            data["config"]["mission"]["type"],
            ["free_explore", "feature_test", "level_design_reverse"],
        )
        self.assertIn("codex_exec", [runner["id"] for runner in data["runners"]])
        self.assertIn("claude_print", [runner["id"] for runner in data["runners"]])
        self.assertGreaterEqual(len(data["run"]["steps"]), 3)
        self.assertIn("session_dir", data["run"]["outputs"])
        self.assertIn("final_report", data["run"]["outputs"])
        self.assertEqual(data["config"]["allowed_actions"], ["screenshot", "wait", "back"])
        self.assertNotIn("tap", data["config"]["allowed_actions"])
        self.assertNotIn("swipe", data["config"]["allowed_actions"])
        step_actions = [step["action"]["type"] for step in data["run"]["steps"]]
        self.assertNotIn("tap", step_actions)
        self.assertNotIn("swipe", step_actions)

    def test_app_declares_static_only_boundary(self):
        script = (WEB_DIR / "app.js").read_text(encoding="utf-8")

        self.assertIn("STATIC_ONLY", script)
        self.assertIn("selectedRunnerId", script)
        self.assertIn("fetch(sampleUrl)", script)
        self.assertIn("pollRun", script)
        self.assertIn("/api/runs/", script)
        self.assertIn("runner: selectedRunnerId", script)
        self.assertIn("renderRunners", script)
        self.assertIn("getUnsafeActionsEnabled", script)
        self.assertIn("getEffectiveAllowedActions", script)
        self.assertIn("wireUnsafeActionToggle", script)
        self.assertRegex(script, r"enable_unsafe_actions:\s*getUnsafeActionsEnabled\(\)")
        self.assertIn('const UNSAFE_ACTIONS = ["tap", "swipe"];', script)
        self.assertNotIn("enable_unsafe_actions: true", script)
        self.assertNotIn("child_process", script)
        self.assertNotIn("codex exec", script)
        self.assertNotIn("claude -p", script)

    def test_touched_web_files_use_readable_chinese(self):
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        script = (WEB_DIR / "app.js").read_text(encoding="utf-8")

        self.assertIn("任务配置", html)
        self.assertIn("执行器选择", html)
        self.assertIn("交互权限", html)
        self.assertIn("允许点击/滑动", html)
        self.assertIn("真实点击或滑动", html)
        self.assertIn("开始运行", html)
        self.assertIn("后端在线", script)
        self.assertIn("运行完成", script)


if __name__ == "__main__":
    unittest.main()
