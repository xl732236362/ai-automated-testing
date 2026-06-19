# -*- coding: utf-8 -*-
"""Tests for persistent app profile memory."""

import json
import os
import tempfile
import unittest

from game_reverse.memory import PROFILE_SCHEMA_VERSION, ProfileStore, sanitize_app_id


class TestProfileMemory(unittest.TestCase):
    def test_sanitizes_app_id_for_profile_directory(self):
        self.assertEqual(sanitize_app_id("com.example.game"), "com.example.game")
        self.assertEqual(sanitize_app_id("bad/pkg:name"), "bad_pkg_name")

    def test_initializes_profile_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProfileStore(tmpdir, "com.example.game")
            store.initialize(package_name="com.example.game")

            expected_files = [
                "profile.json",
                "state_map.json",
                "affordances.json",
                "safety_rules.json",
                "skills.json",
                "memory.jsonl",
            ]
            for filename in expected_files:
                with self.subTest(filename=filename):
                    self.assertTrue(os.path.exists(os.path.join(store.profile_dir, filename)))

            profile = store.load_json("profile.json", {})

        self.assertEqual(profile["schema_version"], PROFILE_SCHEMA_VERSION)
        self.assertEqual(profile["package_name"], "com.example.game")

    def test_updates_json_atomically_and_appends_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProfileStore(tmpdir, "com.example.game")
            store.initialize(package_name="com.example.game")
            store.update_json("state_map.json", {"version": 1, "states": {"state_a": {}}})
            store.append_memory({"event": "observation", "state_id": "state_a"})

            state_map = store.load_json("state_map.json", {})
            with open(os.path.join(store.profile_dir, "memory.jsonl"), encoding="utf-8") as memory_file:
                memory_events = [json.loads(line) for line in memory_file if line.strip()]

        self.assertIn("state_a", state_map["states"])
        self.assertEqual(memory_events[0]["state_id"], "state_a")

    def test_migrates_missing_schema_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProfileStore(tmpdir, "com.example.game")
            os.makedirs(store.profile_dir)
            with open(os.path.join(store.profile_dir, "profile.json"), "w", encoding="utf-8") as profile_file:
                json.dump({"app_id": "com.example.game"}, profile_file)

            store.initialize(package_name="com.example.game")
            profile = store.load_json("profile.json", {})

        self.assertEqual(profile["schema_version"], PROFILE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
