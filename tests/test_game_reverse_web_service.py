# -*- coding: utf-8 -*-
"""Tests for the local game_reverse web service."""

import os
import tempfile
import threading
import time
import unittest

from game_reverse.executors import CodexExecExecutor, ExecutorRegistry, create_default_registry
from game_reverse.target_discovery import TargetDiscoveryError
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


class FakeDiscovery:
    def __init__(self):
        self.calls = []

    def list_devices(self):
        self.calls.append(("list_devices",))
        return [{"id": "emulator-5554", "uri": "Android:///emulator-5554"}]

    def foreground_app(self, device_id):
        self.calls.append(("foreground_app", device_id))
        return {
            "device_id": device_id,
            "package_name": "com.redlinegames.matchsniper3d",
            "activity": "com.unity3d.player.UnityPlayerActivity",
            "source": "dumpsys activity activities",
        }

    def package_validation(self, device_id, package_name):
        self.calls.append(("package_validation", device_id, package_name))
        return {
            "device_id": device_id,
            "package_name": package_name,
            "installed": True,
            "launchable": True,
            "activity": "com.unity3d.player.UnityPlayerActivity",
            "warnings": [],
        }


class FailingDiscovery(FakeDiscovery):
    def list_devices(self):
        raise TargetDiscoveryError("adb command not found")

    def foreground_app(self, device_id):
        raise TargetDiscoveryError("foreground app not found")

    def package_validation(self, device_id, package_name):
        raise TargetDiscoveryError("invalid package name")


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


class RecordingExecutor:
    id = "recording"
    name = "Recording"
    available = True
    description = "Records the context passed by the Web service."

    def __init__(self):
        self.contexts = []

    def metadata(self):
        return {
            "id": self.id,
            "name": self.name,
            "available": self.available,
            "description": self.description,
        }

    def start(self, config, payload, context=None):
        self.contexts.append(context)
        os.makedirs(context.run_dir, exist_ok=True)
        context.emit_event("runner_event", source=self.id, message="adapter event")
        report_path = os.path.join(context.run_dir, "final_report.md")
        with open(report_path, "w", encoding="utf-8") as report:
            report.write("# Recording Report\n")
        return context.run_dir


class ProgressExecutor(RecordingExecutor):
    id = "progress"
    name = "Progress"
    description = "Emits session progress and waits before completing."

    def __init__(self):
        super().__init__()
        self.release = threading.Event()

    def start(self, config, payload, context=None):
        self.contexts.append(context)
        os.makedirs(context.run_dir, exist_ok=True)
        context.emit_event("session_started", session_dir=context.run_dir)
        context.emit_event(
            "run_progress",
            step=1,
            max_steps=payload.get("max_steps", 1),
            action_type="wait",
            message="第 1 步 / 共 1 步：wait",
        )
        self.release.wait(timeout=5)
        report_path = os.path.join(context.run_dir, "final_report.md")
        with open(report_path, "w", encoding="utf-8") as report:
            report.write("# Progress Report\n")
        return context.run_dir


class FakeServiceProcess:
    def __init__(self, stdout_lines=None, stderr_lines=None, returncode=0):
        self.stdin = FakeServiceStdin()
        self.stdout = stdout_lines or []
        self.stderr = stderr_lines or []
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        pass

    def kill(self):
        pass


class FakeServiceStdin:
    def write(self, text):
        pass

    def flush(self):
        pass

    def close(self):
        pass


class TestGameReverseWebService(unittest.TestCase):
    def make_service(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.runner = FakeRunner()
        return GameReverseWebService(
            output_root=self.tmpdir.name,
            runner=self.runner,
            executors=create_default_registry(self.runner, environ={}),
        )

    def wait_for_status(self, service, run_id, expected_status, timeout=2):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = service.get_run(run_id)
            if last["status"] == expected_status:
                return last
            time.sleep(0.01)
        self.fail("run %s did not reach %s; last=%r" % (run_id, expected_status, last))

    def wait_for_event(self, service, run_id, event_type, timeout=2):
        deadline = time.time() + timeout
        events = []
        while time.time() < deadline:
            events = service.run_events(run_id)
            if any(event["type"] == event_type for event in events):
                return events
            time.sleep(0.01)
        self.fail("run %s did not emit %s; events=%r" % (run_id, event_type, events))

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

    def test_health_uses_executor_registry_metadata(self):
        service = self.make_service()

        health = service.health()

        runners = {runner["id"]: runner for runner in health["runners"]}
        self.assertTrue(runners["game_reverse"]["available"])
        self.assertFalse(runners["codex_exec"]["available"])
        self.assertFalse(runners["claude_print"]["available"])

    def test_lists_devices_through_discovery_boundary(self):
        discovery = FakeDiscovery()
        service = GameReverseWebService(
            runner=FakeRunner(),
            executors=create_default_registry(FakeRunner(), environ={}),
            target_discovery=discovery,
        )

        result = service.list_devices()

        self.assertEqual(result["devices"][0]["id"], "emulator-5554")
        self.assertEqual(discovery.calls, [("list_devices",)])

    def test_reads_foreground_app_through_discovery_boundary(self):
        discovery = FakeDiscovery()
        service = GameReverseWebService(
            runner=FakeRunner(),
            executors=create_default_registry(FakeRunner(), environ={}),
            target_discovery=discovery,
        )

        result = service.foreground_app("emulator-5554")

        self.assertEqual(result["package_name"], "com.redlinegames.matchsniper3d")
        self.assertEqual(discovery.calls, [("foreground_app", "emulator-5554")])

    def test_validates_package_through_discovery_boundary(self):
        discovery = FakeDiscovery()
        service = GameReverseWebService(
            runner=FakeRunner(),
            executors=create_default_registry(FakeRunner(), environ={}),
            target_discovery=discovery,
        )

        result = service.package_validation("emulator-5554", "com.redlinegames.matchsniper3d")

        self.assertTrue(result["launchable"])
        self.assertEqual(
            discovery.calls,
            [("package_validation", "emulator-5554", "com.redlinegames.matchsniper3d")],
        )

    def test_converts_target_discovery_errors_to_validation_errors(self):
        service = GameReverseWebService(
            runner=FakeRunner(),
            executors=create_default_registry(FakeRunner(), environ={}),
            target_discovery=FailingDiscovery(),
        )

        with self.assertRaisesRegex(ValidationError, "adb command not found"):
            service.list_devices()
        with self.assertRaisesRegex(ValidationError, "foreground app not found"):
            service.foreground_app("emulator-5554")
        with self.assertRaisesRegex(ValidationError, "invalid package name"):
            service.package_validation("emulator-5554", "invalid package")

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

    def test_passes_run_context_to_executor_and_records_adapter_events(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        executor = RecordingExecutor()
        registry = ExecutorRegistry([executor])
        service = GameReverseWebService(
            output_root=self.tmpdir.name,
            runner=FakeRunner(),
            executors=registry,
        )
        payload = self.valid_payload()
        payload["runner"] = "recording"

        result = service.start_run(payload)
        completed = self.wait_for_status(service, result["id"], "completed")

        self.assertEqual(len(executor.contexts), 1)
        context = executor.contexts[0]
        self.assertEqual(context.run_id, result["id"])
        self.assertTrue(context.run_dir.startswith(self.tmpdir.name))
        self.assertEqual(completed["session_dir"], context.run_dir)
        events = service.run_events(result["id"])
        self.assertTrue(any(event["type"] == "runner_event" for event in events))
        report = service.session_report(result["id"])
        self.assertIn("# Recording Report", report["final_report"])

    def test_records_session_dir_and_progress_while_run_is_active(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        executor = ProgressExecutor()
        service = GameReverseWebService(
            output_root=self.tmpdir.name,
            runner=FakeRunner(),
            executors=ExecutorRegistry([executor]),
        )
        payload = self.valid_payload()
        payload["runner"] = "progress"

        result = service.start_run(payload)
        running = self.wait_for_status(service, result["id"], "running")

        self.assertEqual(running["session_dir"], executor.contexts[0].run_dir)
        self.wait_for_event(service, result["id"], "session_started")
        events = self.wait_for_event(service, result["id"], "run_progress")
        self.assertTrue(any(event["type"] == "session_started" for event in events))
        self.assertTrue(any(event["type"] == "run_progress" for event in events))

        executor.release.set()
        self.wait_for_status(service, result["id"], "completed")

    def test_web_service_runs_enabled_codex_executor_with_fake_process(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        def fake_popen(args, **kwargs):
            final_path = args[args.index("--output-last-message") + 1]
            with open(final_path, "w", encoding="utf-8") as last_message:
                last_message.write("Codex completed through service")
            return FakeServiceProcess(
                stdout_lines=['{"type": "assistant_message", "message": "service event"}\n'],
                stderr_lines=[],
                returncode=0,
            )

        codex_executor = CodexExecExecutor(
            project_root=os.getcwd(),
            enabled=True,
            popen_factory=fake_popen,
            which=lambda command: command,
        )
        registry = ExecutorRegistry([codex_executor])
        service = GameReverseWebService(
            output_root=self.tmpdir.name,
            runner=FakeRunner(),
            executors=registry,
        )
        payload = self.valid_payload()
        payload["runner"] = "codex_exec"

        result = service.start_run(payload)
        completed = self.wait_for_status(service, result["id"], "completed")

        self.assertEqual(completed["runner"], "codex_exec")
        self.assertTrue(os.path.exists(os.path.join(completed["session_dir"], "final_report.md")))
        events = service.run_events(result["id"])
        self.assertTrue(any(event.get("message") == "service event" for event in events))
        report = service.session_report(result["id"])
        self.assertIn("Codex completed through service", report["final_report"])

    def test_rejects_unknown_runner(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["runner"] = "unknown_runner"

        with self.assertRaisesRegex(ValidationError, "runner"):
            service.start_run(payload)

    def test_rejects_disabled_codex_runner_as_unavailable(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["runner"] = "codex_exec"

        with self.assertRaisesRegex(ValidationError, "not available"):
            service.start_run(payload)

    def test_rejects_disabled_claude_runner_as_unavailable(self):
        service = self.make_service()
        payload = self.valid_payload()
        payload["runner"] = "claude_print"

        with self.assertRaisesRegex(ValidationError, "not available"):
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
