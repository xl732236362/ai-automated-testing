# -*- coding: utf-8 -*-
"""Tests for the local game_reverse web service."""

import os
import tempfile
import threading
import time
import unittest

from game_reverse.web_service import GameReverseWebService, ValidationError


class FakeRunner:
    def __init__(self):
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        os.makedirs(config.output_root, exist_ok=True)
        session_dir = os.path.join(config.output_root, "fake-session")
        os.makedirs(session_dir, exist_ok=True)
        with open(os.path.join(session_dir, "final_report.md"), "w", encoding="utf-8") as report:
            report.write("# Report\n")
        return session_dir


class SlowFakeRunner:
    def __init__(self):
        self.started = False
        self.release = threading.Event()

    def __call__(self, config):
        self.started = True
        self.release.wait(timeout=5)
        session_dir = os.path.join(config.output_root, "slow-session")
        os.makedirs(session_dir, exist_ok=True)
        with open(os.path.join(session_dir, "final_report.md"), "w", encoding="utf-8") as report:
            report.write("# Slow Report\n")
        return session_dir


class TestGameReverseWebService(unittest.TestCase):
    def make_service(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.runner = FakeRunner()
        return GameReverseWebService(output_root=self.tmpdir.name, runner=self.runner)

    def wait_for_status(self, service, run_id, expected_status, timeout=2):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = service.get_run(run_id)
            if last["status"] == expected_status:
                return last
            time.sleep(0.01)
        self.fail("run %s did not reach %s; last=%r" % (run_id, expected_status, last))

    def valid_payload(self):
        return {
            "runner": "game_reverse",
            "device_uri": "Android:///emulator-5554",
            "package_name": "com.example.game",
            "max_steps": 2,
            "mission": {
                "type": "free_explore",
                "goal": "Explore tutorial",
                "targets": ["main button"],
                "success_criteria": ["report written"],
            },
            "allowed_actions": ["screenshot", "wait", "back"],
        }

    def test_health_reports_available_runner(self):
        service = self.make_service()

        health = service.health()

        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["runners"][0]["id"], "game_reverse")
        self.assertTrue(health["runners"][0]["available"])

    def test_start_run_validates_and_invokes_game_reverse_runner(self):
        service = self.make_service()

        result = service.start_run(self.valid_payload())

        self.assertEqual(result["runner"], "game_reverse")
        completed = self.wait_for_status(service, result["id"], "completed")
        self.assertEqual(len(self.runner.configs), 1)
        self.assertEqual(self.runner.configs[0].package_name, "com.example.game")
        self.assertTrue(os.path.exists(os.path.join(completed["session_dir"], "final_report.md")))

    def test_start_run_returns_before_slow_runner_finishes_and_records_events(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        runner = SlowFakeRunner()
        service = GameReverseWebService(output_root=self.tmpdir.name, runner=runner)

        result = service.start_run(self.valid_payload())

        self.assertIn(result["status"], {"queued", "running"})
        self.wait_for_status(service, result["id"], "running")
        self.assertTrue(runner.started)
        events = service.run_events(result["id"])
        self.assertTrue(any(event["type"] == "run_started" for event in events))

        runner.release.set()
        self.wait_for_status(service, result["id"], "completed")
        report = service.session_report(result["id"])

        self.assertIn("# Slow Report", report["final_report"])

    def test_rejects_unknown_runner(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["runner"] = "codex_exec"

        with self.assertRaisesRegex(ValidationError, "runner"):
            service.start_run(payload)

    def test_rejects_tap_without_explicit_opt_in(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["allowed_actions"] = ["screenshot", "wait", "tap"]

        with self.assertRaisesRegex(ValidationError, "enable_unsafe_actions"):
            service.start_run(payload)

    def test_session_report_reads_final_report(self):
        service = self.make_service()
        result = service.start_run(self.valid_payload())
        self.wait_for_status(service, result["id"], "completed")

        report = service.session_report(result["id"])

        self.assertEqual(report["id"], result["id"])
        self.assertIn("# Report", report["final_report"])


if __name__ == "__main__":
    unittest.main()
