# -*- coding: utf-8 -*-
"""Tests for game_reverse mission parsing."""

import unittest

from game_reverse.mission import Mission, parse_mission


class TestGameReverseMission(unittest.TestCase):
    def test_default_mission(self):
        mission = parse_mission(None)

        self.assertIsInstance(mission, Mission)
        self.assertEqual(mission.type, "free_explore")
        self.assertEqual(mission.goal, "自由探索 App/Game 并总结界面与功能")
        self.assertEqual(mission.targets, [])
        self.assertEqual(mission.success_criteria, [])

    def test_feature_test_parsing(self):
        mission = parse_mission(
            {
                "type": "feature_test",
                "goal": "验证登录功能",
                "targets": ["登录页", "用户中心"],
                "success_criteria": ["能成功登录", "显示用户信息"],
            }
        )

        self.assertEqual(mission.type, "feature_test")
        self.assertEqual(mission.goal, "验证登录功能")
        self.assertEqual(mission.targets, ["登录页", "用户中心"])
        self.assertEqual(mission.success_criteria, ["能成功登录", "显示用户信息"])

    def test_unknown_mission_type_rejected(self):
        with self.assertRaisesRegex(ValueError, "mission.type"):
            parse_mission({"type": "unknown", "goal": "探索"})

    def test_explicit_mission_without_goal_rejected(self):
        with self.assertRaisesRegex(ValueError, "mission.goal"):
            parse_mission({"type": "free_explore"})

        with self.assertRaisesRegex(ValueError, "mission.goal"):
            parse_mission({"type": "free_explore", "goal": ""})


if __name__ == "__main__":
    unittest.main()
