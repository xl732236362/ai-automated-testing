# -*- coding: utf-8 -*-
"""Tests for game explorer executor adapters."""

import os
import subprocess
import tempfile
import unittest

from game_reverse.executors import (
    ClaudePrintExecutor,
    CodexExecExecutor,
    ExecutorRegistry,
    GameReverseExecutor,
    create_default_registry,
    validate_repo_root,
)


class FakeProcess:
    def __init__(self, stdout_lines=None, stderr_lines=None, returncode=0):
        self.stdin = FakeStdin()
        self.stdout = stdout_lines or []
        self.stderr = stderr_lines or []
        self.returncode = returncode
        self.pid = 1234
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class FakeStdin:
    def __init__(self):
        self.written = []
        self.closed = False

    def write(self, text):
        self.written.append(text)

    def flush(self):
        pass

    def close(self):
        self.closed = True


class PollingFakeProcess(FakeProcess):
    def __init__(self, return_after_polls=3, returncode=0):
        super().__init__(stdout_lines=[], stderr_lines=[], returncode=returncode)
        self.polls = 0
        self.return_after_polls = return_after_polls

    def poll(self):
        self.polls += 1
        if self.polls >= self.return_after_polls:
            return self.returncode
        return None

    def wait(self, timeout=None):
        return self.returncode


class TimedStdout:
    def __init__(self, lines, clock):
        self.lines = list(lines)
        self.clock = clock

    def __iter__(self):
        for advance_seconds, line in self.lines:
            self.clock.advance(advance_seconds)
            yield line


class ManualClock:
    def __init__(self):
        self.current = 0

    def monotonic(self):
        return self.current

    def advance(self, seconds):
        self.current += seconds

    def sleep(self, seconds):
        self.current += seconds


def make_context(run_id, run_dir, events):
    from game_reverse.executors import ExecutorRunContext

    def emit_event(event_type, **extra):
        event = {"type": event_type}
        event.update(extra)
        events.append(event)

    return ExecutorRunContext(run_id=run_id, run_dir=run_dir, emit_event=emit_event)


class TestExecutorRegistry(unittest.TestCase):
    def test_default_registry_lists_all_runner_metadata(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={},
            codex_which=lambda command: "C:/tools/codex.cmd",
        )

        runners = registry.metadata()

        self.assertEqual(
            [runner["id"] for runner in runners],
            ["game_reverse", "lightweight", "codex_exec", "claude_print"],
        )
        self.assertTrue(runners[0]["available"])
        self.assertFalse(runners[1]["available"])
        self.assertTrue(runners[2]["available"])
        self.assertFalse(runners[3]["available"])

    def test_lightweight_runner_is_available_when_decider_is_injected(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={},
            codex_which=lambda command: None,
            lightweight_decider=object(),
        )

        runners = {runner["id"]: runner for runner in registry.metadata()}

        self.assertTrue(runners["lightweight"]["available"])

    def test_codex_exec_is_available_by_default_when_binary_exists(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={},
            codex_which=lambda command: "C:/tools/codex.cmd",
        )

        runners = {runner["id"]: runner for runner in registry.metadata()}

        self.assertTrue(runners["codex_exec"]["available"])
        self.assertIn("Codex", runners["codex_exec"]["description"])

    def test_codex_exec_is_unavailable_when_binary_missing(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={},
            codex_which=lambda command: None,
        )

        runners = {runner["id"]: runner for runner in registry.metadata()}

        self.assertFalse(runners["codex_exec"]["available"])
        self.assertIn("not found", runners["codex_exec"]["description"])

    def test_codex_exec_reads_environment_options(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={
                "GAME_REVERSE_CODEX_COMMAND": "codex-custom",
                "GAME_REVERSE_CODEX_TIMEOUT_SECONDS": "123",
                "GAME_REVERSE_CODEX_IDLE_TIMEOUT_SECONDS": "45",
                "GAME_REVERSE_CODEX_SANDBOX": "read-only",
                "GAME_REVERSE_CODEX_PROFILE": "local",
                "GAME_REVERSE_CODEX_MODEL": "gpt-5.1-codex",
            },
            codex_which=lambda command: "C:/tools/%s.cmd" % command,
        )

        executor = registry.get("codex_exec")

        self.assertTrue(executor.available)
        self.assertEqual(executor.command, "codex-custom")
        self.assertEqual(executor.timeout_seconds, 123)
        self.assertEqual(executor.idle_timeout_seconds, 45)
        self.assertEqual(executor.sandbox, "read-only")
        self.assertEqual(executor.profile, "local")
        self.assertEqual(executor.model, "gpt-5.1-codex")

    def test_registry_rejects_unknown_runner(self):
        registry = ExecutorRegistry([GameReverseExecutor(lambda config: "session-dir")])

        with self.assertRaisesRegex(KeyError, "missing"):
            registry.get("missing")

    def test_game_reverse_executor_delegates_to_runner_with_optional_context(self):
        calls = []

        def fake_runner(config, context=None, session_name=None):
            calls.append((config, context, session_name))
            return "session-dir"

        executor = GameReverseExecutor(fake_runner)
        context = make_context("run-123", os.path.join(os.getcwd(), "run-123"), [])

        result = executor.start(
            config={"package_name": "com.example.game"},
            payload={},
            context=context,
        )

        self.assertEqual(result, "session-dir")
        self.assertEqual(calls, [({"package_name": "com.example.game"}, context, "run-123")])

    def test_game_reverse_executor_keeps_legacy_runner_compatibility(self):
        calls = []

        def fake_runner(config):
            calls.append(config)
            return "legacy-session"

        executor = GameReverseExecutor(fake_runner)

        result = executor.start({"package_name": "com.example.game"}, payload={}, context=object())

        self.assertEqual(result, "legacy-session")
        self.assertEqual(calls, [{"package_name": "com.example.game"}])

    def test_game_reverse_executor_does_not_swallow_runner_type_errors(self):
        def fake_runner(config, context=None):
            raise TypeError("context object is invalid inside runner")

        executor = GameReverseExecutor(fake_runner)

        with self.assertRaisesRegex(TypeError, "invalid inside runner"):
            executor.start({"package_name": "com.example.game"}, payload={}, context=object())


class TestExecutorCommandBuilders(unittest.TestCase):
    def payload(self):
        return {
            "package_name": "com.example.game",
            "allowed_actions": ["screenshot", "wait", "back"],
            "mission": {
                "type": "free_explore",
                "goal": "Explore tutorial",
                "targets": ["start button"],
                "success_criteria": ["write report"],
            },
            "api_key": "should-not-leak",
            "authorization": "Bearer should-not-leak",
        }

    def test_codex_builds_argument_list_without_shell_string(self):
        executor = CodexExecExecutor(
            project_root=os.getcwd(),
            enabled=True,
            which=lambda command: command,
        )
        prompt = executor.build_prompt(self.payload(), config=None)
        final_message_path = os.path.join(os.getcwd(), "last-message.txt")

        args = executor.build_command(
            prompt,
            repo_root=os.getcwd(),
            final_message_path=final_message_path,
        )

        self.assertEqual(args[:7], [
            "codex",
            "exec",
            "--cd",
            os.path.abspath(os.getcwd()),
            "--sandbox",
            "workspace-write",
            "--json",
        ])
        self.assertIn("--output-last-message", args)
        self.assertEqual(args[args.index("--output-last-message") + 1], final_message_path)
        self.assertEqual(args[-1], "-")
        self.assertNotIn(prompt, args)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", args)
        self.assertTrue(all(isinstance(part, str) for part in args))

    def test_codex_command_includes_profile_and_model_when_configured(self):
        executor = CodexExecExecutor(
            project_root=os.getcwd(),
            enabled=True,
            profile="local",
            model="gpt-5.1-codex",
            which=lambda command: command,
        )
        prompt = executor.build_prompt(self.payload(), config=None)
        final_message_path = os.path.join(os.getcwd(), "last-message.txt")

        args = executor.build_command(
            prompt,
            repo_root=os.getcwd(),
            final_message_path=final_message_path,
        )

        self.assertEqual(args[args.index("--profile") + 1], "local")
        self.assertEqual(args[args.index("--model") + 1], "gpt-5.1-codex")

    def test_codex_command_uses_resolved_binary_path(self):
        resolved_codex = r"C:\tools\codex.CMD"
        executor = CodexExecExecutor(
            project_root=os.getcwd(),
            enabled=True,
            which=lambda command: resolved_codex,
        )
        prompt = executor.build_prompt(self.payload(), config=None)

        args = executor.build_command(prompt, repo_root=os.getcwd())

        self.assertEqual(args[0], resolved_codex)

    def test_claude_builds_argument_list_without_shell_string(self):
        executor = ClaudePrintExecutor(project_root=os.getcwd())
        prompt = executor.build_prompt(self.payload(), config=None)

        args = executor.build_command(prompt)

        self.assertEqual(args, ["claude", "-p", "--output-format", "stream-json", prompt])

    def test_prompt_contains_runtime_context_but_not_secret_like_fields(self):
        prompt = CodexExecExecutor(project_root=os.getcwd()).build_prompt(self.payload(), config=None)

        self.assertIn("Execute this task now", prompt)
        self.assertIn("final answer", prompt)
        self.assertIn("com.example.game", prompt)
        self.assertIn("Explore tutorial", prompt)
        self.assertIn("screenshot, wait, back", prompt)
        self.assertIn("Stay within this repository", prompt)
        self.assertNotIn("should-not-leak", prompt)
        self.assertNotIn("api_key", prompt)
        self.assertNotIn("authorization", prompt)

    def test_prompt_includes_fixed_run_output_contract_when_context_is_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            context = make_context("run-fixed", os.path.join(tmpdir, "run-fixed"), events)

            prompt = CodexExecExecutor(project_root=os.getcwd()).build_prompt(
                self.payload(),
                config=None,
                context=context,
            )

            self.assertIn("Run ID: run-fixed", prompt)
            self.assertIn("Output directory: %s" % os.path.abspath(context.run_dir), prompt)
            self.assertIn("Write all run artifacts into the output directory above", prompt)
            self.assertIn("Do not create a sibling session directory", prompt)
            self.assertIn("final_report.md", prompt)
            self.assertIn("actions.jsonl", prompt)
            self.assertIn("observations.jsonl", prompt)
            self.assertIn("screens/", prompt)

    def test_prompt_includes_gesture_exploration_matrix_when_gestures_are_allowed(self):
        payload = self.payload()
        payload["allowed_actions"] = [
            "screenshot",
            "wait",
            "tap",
            "swipe",
            "hold_drag_release",
        ]

        prompt = CodexExecExecutor(project_root=os.getcwd()).build_prompt(payload, config=None)

        self.assertIn("Gesture exploration matrix", prompt)
        self.assertIn("direct tap on visible objects", prompt)
        self.assertIn("scene drag or swipe", prompt)
        self.assertIn("tap the fire/action button", prompt)
        self.assertIn("hold_drag_release", prompt)
        self.assertIn("press the gameplay control", prompt)
        self.assertIn("drag toward the target", prompt)
        self.assertIn("release", prompt)

    def test_validate_repo_root_rejects_parent_directory(self):
        project_root = os.path.join(os.getcwd(), "project")
        parent = os.path.dirname(project_root)

        with self.assertRaisesRegex(Exception, "repo_root"):
            validate_repo_root(parent, project_root=project_root)


class TestExecutorEventParsers(unittest.TestCase):
    def test_codex_parser_maps_jsonl_events(self):
        lines = [
            '{"type": "started", "message": "run started"}',
            "",
            '{"type": "assistant_message", "message": "observed screen"}',
        ]

        events = CodexExecExecutor().parse_events(lines)

        self.assertEqual([event["type"] for event in events], ["runner_event", "runner_event"])
        self.assertEqual(events[0]["source"], "codex_exec")
        self.assertEqual(events[0]["message"], "run started")

    def test_claude_parser_maps_stream_json_events(self):
        lines = [
            '{"type": "system", "subtype": "init"}',
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "ready"}]}}',
        ]

        events = ClaudePrintExecutor().parse_events(lines)

        self.assertEqual([event["type"] for event in events], ["runner_event", "runner_event"])
        self.assertEqual(events[0]["source"], "claude_print")
        self.assertIn("init", events[0]["message"])
        self.assertEqual(events[1]["message"], "ready")

    def test_invalid_json_line_becomes_parse_error(self):
        events = CodexExecExecutor().parse_events(["not json"])

        self.assertEqual(events[0]["type"], "runner_parse_error")
        self.assertEqual(events[0]["source"], "codex_exec")
        self.assertEqual(events[0]["raw"], {"line": "not json"})

    def test_secret_like_raw_keys_are_redacted(self):
        events = CodexExecExecutor().parse_events([
            '{"message": "done", "api_key": "secret-value", "nested": {"password": "pw"}}'
        ])

        self.assertEqual(events[0]["raw"]["api_key"], "[redacted]")
        self.assertEqual(events[0]["raw"]["nested"]["password"], "[redacted]")


class TestCodexExecProcess(unittest.TestCase):
    def payload(self):
        return {
            "package_name": "com.example.game",
            "device_uri": "Android:///emulator-5554",
            "allowed_actions": ["screenshot", "wait", "back"],
            "max_steps": 2,
            "mission": {
                "type": "free_explore",
                "goal": "Explore tutorial",
                "targets": ["start button"],
                "success_criteria": ["write report"],
            },
        }

    def test_codex_start_streams_events_and_writes_logs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            calls = []
            processes = []

            def fake_popen(args, **kwargs):
                calls.append((args, kwargs))
                final_path = args[args.index("--output-last-message") + 1]
                with open(final_path, "w", encoding="utf-8") as last_message:
                    last_message.write("Final Codex summary")
                process = FakeProcess(
                    stdout_lines=[
                        '{"type": "started", "message": "run started"}\n',
                        '{"type": "assistant_message", "message": "observed screen"}\n',
                    ],
                    stderr_lines=["diagnostic line\n"],
                    returncode=0,
                )
                processes.append(process)
                return process

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                popen_factory=fake_popen,
                which=lambda command: command,
            )
            context = make_context("run-001", os.path.join(tmpdir, "run-001"), events)

            session_dir = executor.start(config=None, payload=self.payload(), context=context)

            self.assertEqual(session_dir, context.run_dir)
            self.assertEqual(calls[0][1]["cwd"], os.path.abspath(os.getcwd()))
            self.assertFalse(calls[0][1]["shell"])
            self.assertEqual(calls[0][1]["stdin"], subprocess.PIPE)
            self.assertIn("Explore tutorial", "".join(processes[0].stdin.written))
            self.assertTrue(processes[0].stdin.closed)
            self.assertTrue(os.path.exists(os.path.join(session_dir, "codex_stdout.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "codex_stderr.log")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "codex_last_message.txt")))
            with open(os.path.join(session_dir, "final_report.md"), encoding="utf-8") as report_file:
                report = report_file.read()
            self.assertIn("Final Codex summary", report)
            self.assertTrue(any(event["type"] == "runner_process_started" for event in events))
            self.assertTrue(any(event.get("message") == "run started" for event in events))
            self.assertTrue(any(event.get("message") == "observed screen" for event in events))
            self.assertTrue(any(event["type"] == "runner_stderr" for event in events))

    def test_codex_preserves_report_written_by_process(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []

            def fake_popen(args, **kwargs):
                run_dir = os.path.dirname(args[args.index("--output-last-message") + 1])
                with open(os.path.join(run_dir, "final_report.md"), "w", encoding="utf-8") as report:
                    report.write("# Real Exploration Report\n\nCodex wrote this report.")
                return FakeProcess(returncode=0)

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                popen_factory=fake_popen,
                which=lambda command: command,
            )
            context = make_context("run-report", os.path.join(tmpdir, "run-report"), events)

            session_dir = executor.start(config=None, payload=self.payload(), context=context)

            with open(os.path.join(session_dir, "final_report.md"), encoding="utf-8") as report_file:
                report = report_file.read()
            self.assertIn("# Real Exploration Report", report)
            self.assertIn("Codex wrote this report.", report)
            self.assertNotIn("# Codex Exec Run", report)
            with open(os.path.join(session_dir, "codex_runner_summary.md"), encoding="utf-8") as summary_file:
                summary = summary_file.read()
            self.assertIn("# Codex Runner Summary", summary)
            self.assertIn("codex_stdout.jsonl", summary)
            self.assertIn("codex_stderr.log", summary)

    def test_codex_timeout_terminates_process_and_emits_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            clock = ManualClock()
            process = PollingFakeProcess(return_after_polls=100)
            terminated = []

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                timeout_seconds=5,
                idle_timeout_seconds=30,
                popen_factory=lambda args, **kwargs: process,
                which=lambda command: command,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
                process_tree_terminator=lambda process: terminated.append(process.pid),
            )
            context = make_context("run-timeout", os.path.join(tmpdir, "run-timeout"), events)

            with self.assertRaisesRegex(Exception, "timed out"):
                executor.start(config=None, payload=self.payload(), context=context)

            self.assertEqual(terminated, [1234])
            self.assertTrue(any(event["type"] == "runner_timeout" for event in events))

    def test_codex_activity_extends_idle_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            clock = ManualClock()
            process = PollingFakeProcess(return_after_polls=5)
            process.stdout = TimedStdout(
                [
                    (4, '{"type": "agent_message", "message": "first progress"}\n'),
                    (4, '{"type": "agent_message", "message": "second progress"}\n'),
                ],
                clock,
            )

            def fake_popen(args, **kwargs):
                final_path = args[args.index("--output-last-message") + 1]
                with open(final_path, "w", encoding="utf-8") as last_message:
                    last_message.write("Completed after progress")
                return process

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                timeout_seconds=30,
                idle_timeout_seconds=5,
                popen_factory=fake_popen,
                which=lambda command: command,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
            )
            context = make_context("run-progress", os.path.join(tmpdir, "run-progress"), events)

            session_dir = executor.start(config=None, payload=self.payload(), context=context)

            self.assertEqual(session_dir, context.run_dir)
            self.assertFalse(process.terminated)
            self.assertTrue(any(event.get("message") == "first progress" for event in events))
            self.assertTrue(any(event.get("message") == "second progress" for event in events))

    def test_codex_idle_timeout_terminates_process_when_no_activity_arrives(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            clock = ManualClock()
            process = PollingFakeProcess(return_after_polls=100)
            terminated = []

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                timeout_seconds=30,
                idle_timeout_seconds=5,
                popen_factory=lambda args, **kwargs: process,
                which=lambda command: command,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
                process_tree_terminator=lambda process: terminated.append(process.pid),
            )
            context = make_context("run-idle-timeout", os.path.join(tmpdir, "run-idle-timeout"), events)

            with self.assertRaisesRegex(Exception, "idle timed out"):
                executor.start(config=None, payload=self.payload(), context=context)

            self.assertEqual(terminated, [1234])
            self.assertTrue(any(
                event["type"] == "runner_idle_timeout" and event["timeout_seconds"] == 5
                for event in events
            ))

    def test_codex_nonzero_exit_emits_failed_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                popen_factory=lambda args, **kwargs: FakeProcess(returncode=7),
                which=lambda command: command,
            )
            context = make_context("run-failed", os.path.join(tmpdir, "run-failed"), events)

            with self.assertRaisesRegex(Exception, "exited with code 7"):
                executor.start(config=None, payload=self.payload(), context=context)

            self.assertTrue(any(
                event["type"] == "runner_process_failed" and event["exit_code"] == 7
                for event in events
            ))

    def test_codex_spawn_error_is_executor_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []

            def fake_popen(args, **kwargs):
                raise OSError("missing binary")

            executor = CodexExecExecutor(
                project_root=os.getcwd(),
                enabled=True,
                popen_factory=fake_popen,
                which=lambda command: command,
            )
            context = make_context("run-spawn-error", os.path.join(tmpdir, "run-spawn-error"), events)

            with self.assertRaisesRegex(Exception, "failed to start codex exec"):
                executor.start(config=None, payload=self.payload(), context=context)


if __name__ == "__main__":
    unittest.main()
