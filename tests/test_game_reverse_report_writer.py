# -*- coding: utf-8 -*-
"""Tests for mission draft and final report writing."""

import json
import os
import tempfile
import unittest

from game_reverse.mission import Mission
from game_reverse.report_writer import update_mission_draft, write_final_report


class TestReportWriter(unittest.TestCase):
    def test_update_mission_draft_appends_evidence_findings(self):
        draft = "# App/Game 探索草稿\n"
        decision = {
            "new_findings": [
                {
                    "category": "任务系统",
                    "claim": "主界面存在任务入口",
                    "evidence": "screens/step_0001.png",
                    "confidence": "medium",
                }
            ],
            "risks": [],
        }

        result = update_mission_draft(draft, step=1, decision=decision)

        self.assertIn("任务系统", result)
        self.assertIn("主界面存在任务入口", result)
        self.assertIn("screens/step_0001.png", result)

    def test_write_feature_test_report_mentions_coverage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            observations_path = os.path.join(tmpdir, "observations.jsonl")
            with open(observations_path, "w", encoding="utf-8") as observations_file:
                observations_file.write(
                    json.dumps(
                        {
                            "step": 1,
                            "mission_type": "feature_test",
                            "state": "main_menu",
                            "screen_summary": "主界面",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

            mission = Mission(type="feature_test", goal="测试任务入口", targets=["任务"])
            write_final_report(tmpdir, "# 草稿", mission, stop_reason="max_steps_reached")

            with open(os.path.join(tmpdir, "final_report.md"), "r", encoding="utf-8") as report_file:
                report = report_file.read()

        self.assertIn("功能测试阶段报告", report)
        self.assertIn("任务", report)
        self.assertIn("main_menu", report)

    def test_write_level_design_report_mentions_level_analysis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "observations.jsonl"), "w", encoding="utf-8").close()
            mission = Mission(type="level_design_reverse", goal="逆推关卡", targets=["关卡列表"])

            write_final_report(tmpdir, "# 草稿", mission, stop_reason="max_steps_reached")

            with open(os.path.join(tmpdir, "final_report.md"), "r", encoding="utf-8") as report_file:
                report = report_file.read()

        self.assertIn("关卡设计逆推报告", report)
        self.assertIn("关卡列表", report)


if __name__ == "__main__":
    unittest.main()
