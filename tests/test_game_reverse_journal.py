# -*- coding: utf-8 -*-
"""Tests for game_reverse journal writing."""

import json
import os
import tempfile
import unittest

from game_reverse.journal import Journal


class TestGameReverseJournal(unittest.TestCase):
    def test_creates_session_files_and_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, session_name="test-session")
            journal.write_action({"step": 1, "result": "executed"})
            journal.write_observation({"step": 1, "state": "main_menu"})

            actions_path = os.path.join(journal.session_dir, "actions.jsonl")
            observations_path = os.path.join(journal.session_dir, "observations.jsonl")

            with open(actions_path, "r", encoding="utf-8") as action_file:
                action = json.loads(action_file.readline())
            with open(observations_path, "r", encoding="utf-8") as observation_file:
                observation = json.loads(observation_file.readline())

        self.assertEqual(action["result"], "executed")
        self.assertEqual(observation["state"], "main_menu")

    def test_updates_mission_draft(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, session_name="test-session")
            journal.update_mission_draft("# Draft\n\n- Main menu found")
            content = journal.read_mission_draft()

        self.assertIn("Main menu found", content)


if __name__ == "__main__":
    unittest.main()
