# -*- coding: utf-8 -*-
"""Tests for game explorer executor adapters."""

import os
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
        self.stdout = stdout_lines or []
        self.stderr = stderr_lines or []
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


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
        )

        runners = registry.metadata()

        self.assertEqual([runner["id"] for runner in runners], ["game_reverse", "codex_exec", "claude_print"])
        self.assertTrue(runners[0]["available"])
        self.assertFalse(runners[1]["available"])
        self.assertFalse(runners[2]["available"])

    def test_codex_exec_is_available_when_enabled_and_binary_exists(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={"GAME_REVERSE_ENABLE_CODEX_EXEC": "1"},
            codex_which=lambda command: "C:/tools/codex.cmd",
        )

        runners = {runner["id"]: runner for runner in registry.metadata()}

        self.assertTrue(runners["codex_exec"]["available"])
        self.assertIn("Codex", runners["codex_exec"]["description"])

    def test_codex_exec_is_unavailable_when_enabled_but_binary_missing(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={"GAME_REVERSE_ENABLE_CODEX_EXEC": "1"},
            codex_which=lambda command: None,
        )

        runners = {runner["id"]: runner for runner in registry.metadata()}

        self.assertFalse(runners["codex_exec"]["available"])
        self.assertIn("not found", runners["codex_exec"]["description"])

    def test_codex_exec_reads_environment_options(self):
        registry = create_default_registry(
            runner=lambda config: "session-dir",
            environ={
                "GAME_REVERSE_ENABLE_CODEX_EXEC": "1",
                "GAME_REVERSE_CODEX_COMMAND": "codex-custom",
                "GAME_REVERSE_CODEX_TIMEOUT_SECONDS": "123",
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
        self.assertEqual(executor.sandbox, "read-only")
        self.assertEqual(executor.profile, "local")
        self.assertEqual(executor.model, "gpt-5.1-codex")

    def test_registry_rejects_unknown_runner(self):
        registry = ExecutorRegistry([GameReverseExecutor(lambda config: "session-dir")])

        with self.assertRaisesRegex(KeyError, "missing"):
            registry.get("missing")

    def test_game_reverse_executor_delegates_to_runner_with_optional_context(self):
        calls = []

        def fake_runner(config):
            calls.append(config)
            return "session-dir"

        executor = GameReverseExecutor(fake_runner)
        context = object()

        result = executor.start(
            config={"package_name": "com.example.game"},
            payload={},
            context=context,
        )

        self.assertEqual(result, "session-dir")
        self.assertEqual(calls, [{"package_name": "com.example.game"}])


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
        self.assertEqual(args[-1], prompt)
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

    def test_claude_builds_argument_list_without_shell_string(self):
        executor = ClaudePrintExecutor(project_root=os.getcwd())
        prompt = executor.build_prompt(self.payload(), config=None)

        args = executor.build_command(prompt)

        self.assertEqual(args, ["claude", "-p", "--output-format", "stream-json", prompt])

    def test_prompt_contains_runtime_context_but_not_secret_like_fields(self):
        prompt = CodexExecExecutor(project_root=os.getcwd()).build_prompt(self.payload(), config=None)

        self.assertIn("com.example.game", prompt)
        self.assertIn("Explore tutorial", prompt)
        self.assertIn("screenshot, wait, back", prompt)
        self.assertIn("Stay within this repository", prompt)
        self.assertNotIn("should-not-leak", prompt)
        self.assertNotIn("api_key", prompt)
        self.assertNotIn("authorization", prompt)

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

            def fake_popen(args, **kwargs):
                calls.append((args, kwargs))
                final_path = args[args.index("--output-last-message") + 1]
                with open(final_path, "w", encoding="utf-8") as last_message:
                    last_message.write("Final Codex summary")
                return FakeProcess(
                    stdout_lines=[
                        '{"type": "started", "message": "run started"}\n',
                        '{"type": "assistant_message", "message": "observed screen"}\n',
                    ],
                    stderr_lines=["diagnostic line\n"],
                    returncode=0,
                )

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


if __name__ == "__main__":
    unittest.main()
