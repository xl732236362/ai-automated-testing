# -*- coding: utf-8 -*-
"""Tests for the mission-driven game_reverse run loop."""

import os
import json
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


class FailingSkillExecutor(FakeExecutor):
    def execute(self, action, screen_path):
        if action["type"] == "tap":
            self.executed.append((action, screen_path))
            raise RuntimeError("skill tap failed")
        return super().execute(action, screen_path)


class ChangingScreenshotExecutor(FakeExecutor):
    def __init__(self):
        super().__init__()
        self.screenshot_count = 0

    def execute(self, action, screen_path):
        self.executed.append((action, screen_path))
        if action["type"] == "screenshot":
            self.screenshot_count += 1
            content = b"menu screen" if self.screenshot_count < 3 else b"gameplay screen"
            with open(screen_path, "wb") as screen_file:
                screen_file.write(content)
        return "executed"


class ByteChangingScreenshotExecutor(FakeExecutor):
    def __init__(self):
        super().__init__()
        self.screenshot_count = 0

    def execute(self, action, screen_path):
        self.executed.append((action, screen_path))
        if action["type"] == "screenshot":
            self.screenshot_count += 1
            with open(screen_path, "wb") as screen_file:
                screen_file.write(("screen-%s" % self.screenshot_count).encode("ascii"))
        return "executed"


class StaticScreenshotCounterDecider:
    def __init__(self):
        self.calls = 0

    def decide(self, screen_path, mission, recent_actions, mission_draft):
        self.calls += 1
        summary = "milk counter 3" if self.calls == 1 else "milk counter changed from 3 to 2"
        return {
            "screen_summary": summary,
            "state": "gameplay",
            "action": {"type": "wait", "seconds": 0},
            "reason": "verify post-action feedback",
            "new_findings": [],
            "screenshot_tags": [],
            "risks": [],
        }


class FakeDecider:
    def __init__(self):
        self.calls = 0

    def decide(self, screen_path, mission, recent_actions, mission_draft):
        self.calls += 1
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


class ChangingSummaryDecider:
    def __init__(self):
        self.calls = 0

    def decide(self, screen_path, mission, recent_actions, mission_draft):
        self.calls += 1
        summary = "milk counter 3" if self.calls == 1 else "milk counter changed from 3 to 2"
        return {
            "screen_summary": summary,
            "state": "gameplay",
            "action": {"type": "wait", "seconds": 0},
            "reason": "observe feedback",
            "new_findings": [],
            "screenshot_tags": [],
            "risks": [],
        }


class StateSequenceDecider:
    def __init__(self):
        self.calls = 0

    def decide(self, screen_path, mission, recent_actions, mission_draft):
        self.calls += 1
        if self.calls < 3:
            state = "main_menu"
            summary = "Main menu with start button"
        else:
            state = "gameplay"
            summary = "Level gameplay started"
        return {
            "screen_summary": summary,
            "state": state,
            "action": {"type": "wait", "seconds": 0},
            "reason": "observe state graph",
            "new_findings": [],
            "screenshot_tags": [state],
            "risks": [],
        }


class AffordanceDecider:
    def __init__(self):
        self.calls = 0

    def decide(self, screen_path, mission, recent_actions, mission_draft):
        self.calls += 1
        return {
            "screen_summary": "Main menu with start button",
            "state": "main_menu",
            "action": {"type": "tap", "x": 150, "y": 230},
            "reason": "tap start candidate",
            "new_findings": [],
            "screenshot_tags": ["home"],
            "risks": [],
            "ocr": [{"text": "Start", "bounds": [100, 200, 220, 260]}],
            "ui_nodes": [{"text": "Start", "class": "Button", "bounds": [102, 201, 222, 261]}],
            "visual_regions": [{"bounds": [500, 900, 700, 1050], "reason": "large button"}],
            "proposed_regions": [{"bounds": [100, 200, 220, 260], "label": "start button"}],
        }


class FakeContext:
    def __init__(self):
        self.events = []

    def emit_event(self, event_type, **extra):
        event = {"type": event_type}
        event.update(extra)
        self.events.append(event)


class TestRunLoop(unittest.TestCase):
    def test_runs_fixed_number_of_steps_with_mission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=2,
                output_root=tmpdir,
                profile_enabled=False,
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

    def test_emits_session_and_step_progress_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=1,
                output_root=tmpdir,
                profile_enabled=False,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )
            context = FakeContext()

            session_dir = run_loop(
                config,
                executor=FakeExecutor(),
                decider=FakeDecider(),
                session_name="progress-session",
                context=context,
            )

        event_types = [event["type"] for event in context.events]
        self.assertIn("session_started", event_types)
        self.assertIn("step_screenshot", event_types)
        self.assertIn("step_action", event_types)
        self.assertIn("run_progress", event_types)
        self.assertIn("run_report_written", event_types)
        self.assertEqual(context.events[0]["session_dir"], session_dir)
        progress = [event for event in context.events if event["type"] == "run_progress"][0]
        self.assertEqual(progress["step"], 1)
        self.assertEqual(progress["max_steps"], 1)
        self.assertEqual(progress["action_type"], "wait")

    def test_records_visual_feedback_result_in_action_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=2,
                output_root=tmpdir,
                profile_enabled=False,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )

            session_dir = run_loop(
                config,
                executor=ByteChangingScreenshotExecutor(),
                decider=ChangingSummaryDecider(),
                session_name="feedback-session",
            )

            with open(os.path.join(session_dir, "actions.jsonl"), encoding="utf-8") as action_file:
                action_lines = action_file.readlines()

        self.assertIn('"feedback_result": "counter_changed"', action_lines[-1])
        self.assertIn('"post_action_screen": "screens\\\\post_step_0002.png"', action_lines[-1])

    def test_uses_post_action_screenshot_for_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=2,
                output_root=tmpdir,
                profile_enabled=False,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )

            session_dir = run_loop(
                config,
                executor=FakeExecutor(),
                decider=StaticScreenshotCounterDecider(),
                session_name="post-action-feedback-session",
            )

            with open(os.path.join(session_dir, "actions.jsonl"), encoding="utf-8") as action_file:
                actions = [json.loads(line) for line in action_file if line.strip()]
            with open(os.path.join(session_dir, "observations.jsonl"), encoding="utf-8") as observation_file:
                observations = [json.loads(line) for line in observation_file if line.strip()]
            post_screen_exists = os.path.exists(os.path.join(session_dir, "screens", "post_step_0002.png"))

        self.assertEqual(actions[-1]["feedback_result"], "no_visible_change")
        self.assertEqual(actions[-1]["visual_diff_score"], 0.0)
        self.assertIn("post_step_0002.png", actions[-1]["post_action_screen"])
        self.assertIn("post_step_0002.png", observations[-1]["post_action_screen"])
        self.assertTrue(post_screen_exists)

    def test_writes_state_graph_artifacts_for_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=3,
                output_root=tmpdir,
                profile_enabled=False,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )

            session_dir = run_loop(
                config,
                executor=ChangingScreenshotExecutor(),
                decider=StateSequenceDecider(),
                session_name="state-graph-session",
            )

            state_map_path = os.path.join(session_dir, "state_map.json")
            transitions_path = os.path.join(session_dir, "state_transitions.jsonl")
            observations_path = os.path.join(session_dir, "observations.jsonl")

            with open(state_map_path, "r", encoding="utf-8") as state_map_file:
                state_map = json.load(state_map_file)
            with open(transitions_path, "r", encoding="utf-8") as transition_file:
                transitions = [json.loads(line) for line in transition_file if line.strip()]
            with open(observations_path, "r", encoding="utf-8") as observation_file:
                observations = [json.loads(line) for line in observation_file if line.strip()]

        self.assertEqual(state_map["version"], 1)
        self.assertEqual(len(state_map["states"]), 2)
        self.assertTrue(all(observation.get("state_id") for observation in observations))
        self.assertTrue(all(observation.get("screenshot_hash", "").startswith("sha256:") for observation in observations))
        self.assertTrue(
            all(state.get("screenshot_hash", "").startswith("sha256:") for state in state_map["states"].values())
        )
        self.assertIn("no_change", [transition["classification"] for transition in transitions])
        self.assertIn("entered_new_state", [transition["classification"] for transition in transitions])

    def test_writes_affordance_artifacts_for_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=2,
                output_root=tmpdir,
                profile_enabled=False,
                allowed_actions=["screenshot", "tap"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )

            session_dir = run_loop(
                config,
                executor=FakeExecutor(),
                decider=AffordanceDecider(),
                session_name="affordance-session",
            )

            affordances_path = os.path.join(session_dir, "affordances.json")
            observations_path = os.path.join(session_dir, "observations.jsonl")
            with open(affordances_path, "r", encoding="utf-8") as affordances_file:
                affordances = json.load(affordances_file)
            with open(observations_path, "r", encoding="utf-8") as observation_file:
                observations = [json.loads(line) for line in observation_file if line.strip()]

        state_id = observations[0]["state_id"]
        state_affordances = affordances["states"][state_id]
        start_affordance = [item for item in state_affordances if item["label"] == "Start"][0]

        self.assertEqual(len(state_affordances), 2)
        self.assertEqual(start_affordance["last_result"], "no_visible_change")
        self.assertEqual(start_affordance["status"], "deprioritized")

    def test_records_richer_visual_feedback_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=2,
                output_root=tmpdir,
                profile_enabled=False,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )

            session_dir = run_loop(
                config,
                executor=ByteChangingScreenshotExecutor(),
                decider=FakeDecider(),
                session_name="rich-feedback-session",
            )

            with open(os.path.join(session_dir, "actions.jsonl"), encoding="utf-8") as action_file:
                actions = [json.loads(line) for line in action_file if line.strip()]

        self.assertIn("feedback_confidence", actions[-1])
        self.assertGreater(actions[-1]["visual_diff_score"], 0)
        self.assertEqual(actions[-1]["recovery_reason"], "")
        self.assertEqual(actions[-1]["recommended_actions"], [])

    def test_records_recovery_policy_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=2,
                output_root=tmpdir,
                profile_enabled=False,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )

            session_dir = run_loop(
                config,
                executor=FakeExecutor(),
                decider=FakeDecider(),
                session_name="recovery-policy-session",
            )

            with open(os.path.join(session_dir, "actions.jsonl"), encoding="utf-8") as action_file:
                actions = [json.loads(line) for line in action_file if line.strip()]

        self.assertEqual(actions[-1]["recovery_reason"], "repeated no-change feedback")
        self.assertIn("hold_drag_release", actions[-1]["recommended_actions"])

    def test_persists_profile_memory_across_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = os.path.join(tmpdir, "sessions")
            profile_root = os.path.join(tmpdir, "profiles")
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=1,
                output_root=output_root,
                profile_root=profile_root,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )

            run_loop(
                config,
                executor=FakeExecutor(),
                decider=FakeDecider(),
                session_name="profile-run-one",
            )
            run_loop(
                config,
                executor=FakeExecutor(),
                decider=FakeDecider(),
                session_name="profile-run-two",
            )

            profile_dir = os.path.join(profile_root, "com.example.game")
            with open(os.path.join(profile_dir, "profile.json"), encoding="utf-8") as profile_file:
                profile = json.load(profile_file)
            with open(os.path.join(profile_dir, "state_map.json"), encoding="utf-8") as state_file:
                state_map = json.load(state_file)
            with open(os.path.join(profile_dir, "affordances.json"), encoding="utf-8") as affordance_file:
                affordances = json.load(affordance_file)
            with open(os.path.join(profile_dir, "safety_rules.json"), encoding="utf-8") as safety_file:
                safety_rules = json.load(safety_file)
            with open(os.path.join(profile_dir, "memory.jsonl"), encoding="utf-8") as memory_file:
                memory_events = [json.loads(line) for line in memory_file if line.strip()]

        self.assertEqual(profile["package_name"], "com.example.game")
        self.assertTrue(state_map["states"])
        self.assertIn("states", affordances)
        self.assertIn("sensitive_states", safety_rules)
        self.assertGreaterEqual(len(memory_events), 2)
        self.assertEqual({event["session_name"] for event in memory_events}, {"profile-run-one", "profile-run-two"})

    def test_writes_goal_artifacts_for_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=1,
                output_root=tmpdir,
                profile_enabled=False,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="Explore safely", targets=["玩法"]),
            )

            session_dir = run_loop(
                config,
                executor=FakeExecutor(),
                decider=FakeDecider(),
                session_name="goal-session",
            )

            with open(os.path.join(session_dir, "goals.json"), encoding="utf-8") as goals_file:
                goals = json.load(goals_file)
            with open(os.path.join(session_dir, "goal_events.jsonl"), encoding="utf-8") as events_file:
                events = [json.loads(line) for line in events_file if line.strip()]
            with open(os.path.join(session_dir, "actions.jsonl"), encoding="utf-8") as action_file:
                actions = [json.loads(line) for line in action_file if line.strip()]

        self.assertEqual(goals["main_goal"], "Explore safely")
        self.assertTrue(events)
        self.assertIn("active_subgoal", actions[0])

    def test_uses_profile_skill_before_decider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = os.path.join(tmpdir, "sessions")
            profile_root = os.path.join(tmpdir, "profiles")
            profile_dir = os.path.join(profile_root, "com.example.game")
            os.makedirs(profile_dir)
            with open(os.path.join(profile_dir, "skills.json"), "w", encoding="utf-8") as skills_file:
                json.dump(
                    {
                        "version": 1,
                        "skills": [
                            {
                                "name": "wait_on_unknown",
                                "trigger": {"state_labels": ["unknown"]},
                                "steps": [{"type": "wait", "seconds": 1}],
                                "confidence": 0.8,
                            }
                        ],
                    },
                    skills_file,
                )
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=1,
                output_root=output_root,
                profile_root=profile_root,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )
            decider = FakeDecider()
            executor = FakeExecutor()

            session_dir = run_loop(
                config,
                executor=executor,
                decider=decider,
                session_name="skill-run",
            )

            with open(os.path.join(session_dir, "actions.jsonl"), encoding="utf-8") as action_file:
                actions = [json.loads(line) for line in action_file if line.strip()]
            with open(os.path.join(session_dir, "skill_attempts.jsonl"), encoding="utf-8") as attempt_file:
                attempts = [json.loads(line) for line in attempt_file if line.strip()]

        self.assertEqual(decider.calls, 0)
        self.assertEqual(actions[0]["action_source"], "skill")
        self.assertEqual(attempts[0]["skill_name"], "wait_on_unknown")
        self.assertTrue(attempts[0]["success"])

    def test_failed_profile_skill_falls_back_to_decider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = os.path.join(tmpdir, "sessions")
            profile_root = os.path.join(tmpdir, "profiles")
            profile_dir = os.path.join(profile_root, "com.example.game")
            os.makedirs(profile_dir)
            with open(os.path.join(profile_dir, "skills.json"), "w", encoding="utf-8") as skills_file:
                json.dump(
                    {
                        "version": 1,
                        "skills": [
                            {
                                "name": "tap_unknown",
                                "trigger": {"state_labels": ["unknown"]},
                                "steps": [{"type": "tap", "x": 10, "y": 20}],
                                "confidence": 0.8,
                            }
                        ],
                    },
                    skills_file,
                )
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=1,
                output_root=output_root,
                profile_root=profile_root,
                allowed_actions=["screenshot", "tap", "wait"],
                mission=Mission(type="free_explore", goal="探索任务", targets=["玩法"]),
            )
            decider = FakeDecider()

            session_dir = run_loop(
                config,
                executor=FailingSkillExecutor(),
                decider=decider,
                session_name="skill-fallback-run",
            )

            with open(os.path.join(session_dir, "actions.jsonl"), encoding="utf-8") as action_file:
                actions = [json.loads(line) for line in action_file if line.strip()]
            with open(os.path.join(session_dir, "skill_attempts.jsonl"), encoding="utf-8") as attempt_file:
                attempts = [json.loads(line) for line in attempt_file if line.strip()]

        self.assertEqual(decider.calls, 1)
        self.assertFalse(attempts[0]["success"])
        self.assertEqual(actions[0]["action_source"], "llm")


if __name__ == "__main__":
    unittest.main()
