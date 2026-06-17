# -*- coding: utf-8 -*-
"""Tests for game explorer executor adapters."""

import os
import unittest

from game_reverse.executors import (
    ClaudePrintExecutor,
    CodexExecExecutor,
    ExecutorRegistry,
    GameReverseExecutor,
    create_default_registry,
    validate_repo_root,
)


class TestExecutorRegistry(unittest.TestCase):
    def test_default_registry_lists_all_runner_metadata(self):
        registry = create_default_registry(runner=lambda config: "session-dir")

        runners = registry.metadata()

        self.assertEqual([runner["id"] for runner in runners], ["game_reverse", "codex_exec", "claude_print"])
        self.assertTrue(runners[0]["available"])
        self.assertFalse(runners[1]["available"])
        self.assertFalse(runners[2]["available"])

    def test_registry_rejects_unknown_runner(self):
        registry = ExecutorRegistry([GameReverseExecutor(lambda config: "session-dir")])

        with self.assertRaisesRegex(KeyError, "missing"):
            registry.get("missing")

    def test_game_reverse_executor_delegates_to_runner(self):
        calls = []

        def fake_runner(config):
            calls.append(config)
            return "session-dir"

        executor = GameReverseExecutor(fake_runner)

        result = executor.start(config={"package_name": "com.example.game"}, payload={})

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
        executor = CodexExecExecutor(project_root=os.getcwd())
        prompt = executor.build_prompt(self.payload(), config=None)

        args = executor.build_command(prompt, repo_root=os.getcwd())

        self.assertEqual(args[:5], ["codex", "exec", "--cd", os.path.abspath(os.getcwd()), "--json"])
        self.assertEqual(args[5], prompt)
        self.assertTrue(all(isinstance(part, str) for part in args))

    def test_claude_builds_argument_list_without_shell_string(self):
        executor = ClaudePrintExecutor(project_root=os.getcwd())
        prompt = executor.build_prompt(self.payload(), config=None)

        args = executor.build_command(prompt)

        self.assertEqual(args, ["claude", "-p", "--output-format", "stream-json", prompt])

    def test_prompt_contains_mission_context_but_not_secret_like_fields(self):
        prompt = CodexExecExecutor(project_root=os.getcwd()).build_prompt(self.payload(), config=None)

        self.assertIn("com.example.game", prompt)
        self.assertIn("Explore tutorial", prompt)
        self.assertIn("screenshot, wait, back", prompt)
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


if __name__ == "__main__":
    unittest.main()
