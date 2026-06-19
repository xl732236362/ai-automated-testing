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

    def test_writes_affordance_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, session_name="test-session")
            journal.write_affordances(
                {
                    "version": 1,
                    "states": {"state_abc": [{"id": "aff_abc", "bounds": [1, 2, 3, 4]}]},
                }
            )

            affordances_path = os.path.join(journal.session_dir, "affordances.json")
            with open(affordances_path, "r", encoding="utf-8") as affordances_file:
                affordances = json.load(affordances_file)

        self.assertEqual(affordances["states"]["state_abc"][0]["id"], "aff_abc")

    def test_writes_skill_attempts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, session_name="test-session")
            journal.write_skill_attempt(
                {
                    "step": 1,
                    "skill_name": "close_popup",
                    "success": True,
                }
            )

            attempts_path = os.path.join(journal.session_dir, "skill_attempts.jsonl")
            with open(attempts_path, "r", encoding="utf-8") as attempt_file:
                attempt = json.loads(attempt_file.readline())

        self.assertEqual(attempt["skill_name"], "close_popup")

    def test_writes_goal_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, session_name="test-session")
            journal.write_goal_event({"step": 1, "event": "subgoal_progress"})
            journal.write_goals(
                {
                    "version": 1,
                    "main_goal": "Explore",
                    "active_subgoal": "stabilize launch state",
                    "completed_subgoals": [],
                    "blocked_subgoals": [],
                    "next_candidates": [],
                }
            )

            events_path = os.path.join(journal.session_dir, "goal_events.jsonl")
            goals_path = os.path.join(journal.session_dir, "goals.json")
            with open(events_path, "r", encoding="utf-8") as events_file:
                event = json.loads(events_file.readline())
            with open(goals_path, "r", encoding="utf-8") as goals_file:
                goals = json.load(goals_file)

        self.assertEqual(event["event"], "subgoal_progress")
        self.assertEqual(goals["main_goal"], "Explore")


if __name__ == "__main__":
    unittest.main()
