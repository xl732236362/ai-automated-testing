# -*- coding: utf-8 -*-
"""Tests for game_reverse config loading."""

import json
import tempfile
import unittest
from pathlib import Path

from game_reverse.config import DEFAULT_ALLOWED_ACTIONS, load_config


class TestGameReverseConfig(unittest.TestCase):
    def write_config(self, data):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "config.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def test_config_loads_user_values_and_defaults_including_mission(self):
        path = self.write_config(
            {
                "device_uri": "Android://127.0.0.1:5037/device",
                "package_name": "com.example.game",
                "max_steps": 12,
                "mission": {
                    "type": "feature_test",
                    "goal": "Verify inventory feature",
                    "targets": ["inventory entry"],
                    "success_criteria": ["inventory opens"],
                },
            }
        )

        config = load_config(path)

        self.assertEqual(config.device_uri, "Android://127.0.0.1:5037/device")
        self.assertEqual(config.package_name, "com.example.game")
        self.assertEqual(config.max_steps, 12)
        self.assertEqual(config.mission.type, "feature_test")
        self.assertEqual(config.mission.goal, "Verify inventory feature")
        self.assertEqual(config.mission.targets, ["inventory entry"])
        self.assertEqual(config.mission.success_criteria, ["inventory opens"])
        self.assertEqual(config.model, "gpt-5.5")
        self.assertEqual(config.output_root, "game_reverse/outputs/sessions")
        self.assertEqual(config.allowed_actions, DEFAULT_ALLOWED_ACTIONS)
        self.assertIsNot(config.allowed_actions, DEFAULT_ALLOWED_ACTIONS)
        self.assertEqual(config.recent_steps, 5)
        self.assertEqual(config.llm_retry_count, 1)
        self.assertEqual(config.consecutive_failure_limit, 3)
        self.assertEqual(config.profile_root, "game_reverse/profiles")
        self.assertTrue(config.profile_enabled)
        self.assertFalse(config.enable_continuous_actions)

    def test_default_allowed_actions_do_not_include_hold_drag_release(self):
        self.assertNotIn("hold_drag_release", DEFAULT_ALLOWED_ACTIONS)

        path = self.write_config({"package_name": "com.example.game"})
        config = load_config(path)

        self.assertNotIn("hold_drag_release", config.allowed_actions)

    def test_missing_package_name_rejected(self):
        path = self.write_config({"device_uri": "Android://device"})

        with self.assertRaisesRegex(ValueError, "package_name"):
            load_config(path)

    def test_device_uri_defaults_to_android(self):
        path = self.write_config({"package_name": "com.example.game"})

        config = load_config(path)

        self.assertEqual(config.device_uri, "Android:///")

    def test_non_positive_max_steps_rejected(self):
        for max_steps in (0, -1):
            with self.subTest(max_steps=max_steps):
                path = self.write_config(
                    {"package_name": "com.example.game", "max_steps": max_steps}
                )

                with self.assertRaisesRegex(ValueError, "max_steps"):
                    load_config(path)

    def test_profile_options_can_be_overridden(self):
        path = self.write_config(
            {
                "package_name": "com.example.game",
                "profile_root": "tmp/profiles",
                "profile_enabled": False,
            }
        )

        config = load_config(path)

        self.assertEqual(config.profile_root, "tmp/profiles")
        self.assertFalse(config.profile_enabled)

    def test_continuous_actions_can_be_enabled(self):
        path = self.write_config(
            {
                "package_name": "com.example.game",
                "enable_continuous_actions": True,
            }
        )

        config = load_config(path)

        self.assertTrue(config.enable_continuous_actions)


if __name__ == "__main__":
    unittest.main()
