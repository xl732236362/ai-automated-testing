# -*- coding: utf-8 -*-
"""Tests for run-local state graph tracking."""

import unittest

from game_reverse.state_graph import StateGraph


class TestStateGraph(unittest.TestCase):
    def test_reuses_state_id_for_repeated_screen_signature(self):
        graph = StateGraph()

        first = graph.update(
            step=1,
            screen_path="screens/step_0001.png",
            observation={
                "state": "main_menu",
                "screen_summary": "Main menu with start button",
                "screenshot_tags": ["home"],
            },
        )
        second = graph.update(
            step=2,
            screen_path="screens/step_0002.png",
            observation={
                "state": "main_menu",
                "screen_summary": "Main menu with start button",
                "screenshot_tags": ["home"],
            },
        )

        self.assertEqual(first["state_id"], second["state_id"])
        self.assertEqual(second["transition"]["classification"], "no_change")
        self.assertEqual(second["state_visit_count"], 2)

    def test_creates_new_state_for_different_screen_signature(self):
        graph = StateGraph()

        first = graph.update(
            step=1,
            screen_path="screens/step_0001.png",
            observation={"state": "main_menu", "screen_summary": "Main menu"},
        )
        second = graph.update(
            step=2,
            screen_path="screens/step_0002.png",
            observation={"state": "gameplay", "screen_summary": "Level started"},
        )

        self.assertNotEqual(first["state_id"], second["state_id"])
        self.assertEqual(second["transition"]["classification"], "entered_new_state")
        self.assertEqual(second["transition"]["from_state_id"], first["state_id"])
        self.assertEqual(second["transition"]["to_state_id"], second["state_id"])

    def test_state_map_is_json_serializable_and_readable(self):
        graph = StateGraph()
        graph.update(
            step=1,
            screen_path="screens/step_0001.png",
            observation={"state": "home", "screen_summary": "Home screen"},
        )
        graph.update(
            step=2,
            screen_path="screens/step_0002.png",
            observation={"state": "home", "screen_summary": "Home screen"},
        )

        state_map = graph.to_state_map()

        self.assertEqual(state_map["version"], 1)
        self.assertIn("states", state_map)
        self.assertIn("transitions", state_map)
        self.assertEqual(len(state_map["states"]), 1)
        self.assertEqual(len(state_map["transitions"]), 2)


if __name__ == "__main__":
    unittest.main()
