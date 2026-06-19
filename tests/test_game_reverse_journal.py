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

    def test_writes_state_graph_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, session_name="test-session")
            journal.write_state_transition(
                {
                    "step": 1,
                    "from_state_id": None,
                    "to_state_id": "state_abc",
                    "classification": "entered_new_state",
                }
            )
            journal.write_state_map(
                {
                    "version": 1,
                    "states": {"state_abc": {"state_id": "state_abc"}},
                    "transitions": [],
                }
            )

            transitions_path = os.path.join(journal.session_dir, "state_transitions.jsonl")
            state_map_path = os.path.join(journal.session_dir, "state_map.json")

            with open(transitions_path, "r", encoding="utf-8") as transition_file:
                transition = json.loads(transition_file.readline())
            with open(state_map_path, "r", encoding="utf-8") as state_map_file:
                state_map = json.load(state_map_file)

        self.assertEqual(transition["to_state_id"], "state_abc")
        self.assertEqual(state_map["states"]["state_abc"]["state_id"], "state_abc")


if __name__ == "__main__":
    unittest.main()
