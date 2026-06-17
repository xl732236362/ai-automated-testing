# App/Game Explorer Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a first-version mission-driven App/Game explorer that uses Claude API vision to decide safe Airtest actions on an Android emulator, records each exploration step, and produces mission-specific drafts and reports.

**Architecture:** Add a small standalone Python package under `game_reverse/` so the upstream Airtest core remains untouched. The loop is modular: config loading, mission validation, safe action validation, Airtest execution, Claude API decision, journaling, and mission-specific report writing. Tests avoid real devices and real Claude API calls by injecting fakes.

**Tech Stack:** Python, Airtest core API, Anthropic Python SDK as an optional runtime dependency, `unittest`/`pytest`-compatible tests, JSONL logs, Markdown reports.

---

## Prerequisites

- Work from repository root: `F:/Ugit/Airtest`.
- Runtime optional dependency for real Claude calls: `pip install anthropic`.
- Test commands below use `python -m pytest`; if pytest is unavailable, use `python -m unittest <module>` for the same test file.
- Do not run real-device integration tests unless an Android emulator is connected and the user explicitly wants it.
- Do not commit unless the user explicitly asks. Commit steps are included as handoff guidance only.

## Task 1: Create Package Skeleton, Mission Model, and Config Loader

**Files:**
- Create: `game_reverse/__init__.py`
- Create: `game_reverse/mission.py`
- Create: `game_reverse/config.py`
- Create: `game_reverse/config.example.json`
- Create: `tests/test_game_reverse_config.py`
- Create: `tests/test_game_reverse_mission.py`

**Step 1: Write the failing mission tests**

Create `tests/test_game_reverse_mission.py`:

```python
# encoding=utf-8
import unittest

from game_reverse.mission import Mission, parse_mission


class TestMission(unittest.TestCase):

    def test_defaults_to_free_explore(self):
        mission = parse_mission(None)
        self.assertEqual(mission.type, "free_explore")
        self.assertEqual(mission.goal, "自由探索 App/Game 并总结界面与功能")
        self.assertEqual(mission.targets, [])
        self.assertEqual(mission.success_criteria, [])

    def test_parses_feature_test(self):
        mission = parse_mission({
            "type": "feature_test",
            "goal": "测试任务和商店入口",
            "targets": ["任务", "商店"],
            "success_criteria": ["每个入口至少保存一张截图"]
        })
        self.assertEqual(mission.type, "feature_test")
        self.assertEqual(mission.targets, ["任务", "商店"])

    def test_rejects_unknown_mission_type(self):
        with self.assertRaises(ValueError) as ctx:
            parse_mission({"type": "unknown", "goal": "x"})
        self.assertIn("mission.type", str(ctx.exception))

    def test_requires_goal_for_explicit_mission(self):
        with self.assertRaises(ValueError) as ctx:
            parse_mission({"type": "level_design_reverse"})
        self.assertIn("mission.goal", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Write the failing config tests**

Create `tests/test_game_reverse_config.py`:

```python
# encoding=utf-8
import json
import os
import tempfile
import unittest

from game_reverse.config import load_config


class TestGameReverseConfig(unittest.TestCase):

    def test_loads_defaults_and_user_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "device_uri": "Android:///emulator-5554",
                    "package_name": "com.example.game",
                    "max_steps": 10,
                    "mission": {
                        "type": "feature_test",
                        "goal": "测试任务入口",
                        "targets": ["任务"]
                    }
                }, f)

            config = load_config(config_path)

        self.assertEqual(config.device_uri, "Android:///emulator-5554")
        self.assertEqual(config.package_name, "com.example.game")
        self.assertEqual(config.max_steps, 10)
        self.assertEqual(config.model, "claude-opus-4-8")
        self.assertEqual(config.output_root, "game_reverse/outputs/sessions")
        self.assertEqual(config.allowed_actions, ["screenshot", "wait", "back"])
        self.assertEqual(config.mission.type, "feature_test")
        self.assertEqual(config.mission.targets, ["任务"])

    def test_rejects_missing_package_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"device_uri": "Android:///"}, f)

            with self.assertRaises(ValueError) as ctx:
                load_config(config_path)

        self.assertIn("package_name", str(ctx.exception))

    def test_rejects_non_positive_max_steps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "device_uri": "Android:///",
                    "package_name": "com.example.game",
                    "max_steps": 0
                }, f)

            with self.assertRaises(ValueError) as ctx:
                load_config(config_path)

        self.assertIn("max_steps", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

**Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_game_reverse_mission.py tests/test_game_reverse_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'game_reverse'`.

**Step 4: Write minimal implementation**

Create `game_reverse/__init__.py`:

```python
# encoding=utf-8
```

Create `game_reverse/mission.py`:

```python
# encoding=utf-8
from dataclasses import dataclass, field
from typing import List


MISSION_TYPES = {"free_explore", "feature_test", "level_design_reverse"}


@dataclass
class Mission:
    type: str = "free_explore"
    goal: str = "自由探索 App/Game 并总结界面与功能"
    targets: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)


def parse_mission(raw):
    if raw is None:
        return Mission()
    if not isinstance(raw, dict):
        raise ValueError("mission must be an object")

    mission_type = raw.get("type", "free_explore")
    if mission_type not in MISSION_TYPES:
        raise ValueError("mission.type must be one of: %s" % ", ".join(sorted(MISSION_TYPES)))

    goal = raw.get("goal")
    if not goal:
        raise ValueError("mission.goal is required")

    targets = raw.get("targets", [])
    success_criteria = raw.get("success_criteria", [])
    if not isinstance(targets, list):
        raise ValueError("mission.targets must be a list")
    if not isinstance(success_criteria, list):
        raise ValueError("mission.success_criteria must be a list")

    return Mission(
        type=mission_type,
        goal=goal,
        targets=targets,
        success_criteria=success_criteria,
    )
```

Create `game_reverse/config.py`:

```python
# encoding=utf-8
import json
from dataclasses import dataclass, field
from typing import List

from game_reverse.mission import Mission, parse_mission


DEFAULT_ALLOWED_ACTIONS = ["screenshot", "wait", "back"]


@dataclass
class GameReverseConfig:
    device_uri: str
    package_name: str
    max_steps: int
    mission: Mission = field(default_factory=Mission)
    model: str = "claude-opus-4-8"
    output_root: str = "game_reverse/outputs/sessions"
    allowed_actions: List[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_ACTIONS))
    recent_steps: int = 5
    llm_retry_count: int = 1
    consecutive_failure_limit: int = 3


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not raw.get("package_name"):
        raise ValueError("package_name is required")

    max_steps = raw.get("max_steps", 50)
    if not isinstance(max_steps, int) or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")

    allowed_actions = raw.get("allowed_actions") or list(DEFAULT_ALLOWED_ACTIONS)

    return GameReverseConfig(
        device_uri=raw.get("device_uri", "Android:///"),
        package_name=raw["package_name"],
        max_steps=max_steps,
        mission=parse_mission(raw.get("mission")),
        model=raw.get("model", "claude-opus-4-8"),
        output_root=raw.get("output_root", "game_reverse/outputs/sessions"),
        allowed_actions=allowed_actions,
        recent_steps=raw.get("recent_steps", 5),
        llm_retry_count=raw.get("llm_retry_count", 1),
        consecutive_failure_limit=raw.get("consecutive_failure_limit", 3),
    )
```

Create `game_reverse/config.example.json`:

```json
{
  "device_uri": "Android:///",
  "package_name": "com.example.game",
  "max_steps": 10,
  "model": "claude-opus-4-8",
  "output_root": "game_reverse/outputs/sessions",
  "allowed_actions": ["screenshot", "wait", "back"],
  "recent_steps": 5,
  "llm_retry_count": 1,
  "consecutive_failure_limit": 3,
  "mission": {
    "type": "free_explore",
    "goal": "自由探索 App/Game 并总结界面与功能",
    "targets": [],
    "success_criteria": []
  }
}
```

**Step 5: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/test_game_reverse_mission.py tests/test_game_reverse_config.py -v
```

Expected: PASS.

**Step 6: Commit**

Only if the user asked for commits:

```bash
git add game_reverse/__init__.py game_reverse/mission.py game_reverse/config.py game_reverse/config.example.json tests/test_game_reverse_mission.py tests/test_game_reverse_config.py
git commit -m "Add mission-driven explorer config"
```

---

## Task 2: Add Safe Action Schema and Validator

**Files:**
- Create: `game_reverse/actions.py`
- Create: `tests/test_game_reverse_actions.py`

**Step 1: Write the failing tests**

Create `tests/test_game_reverse_actions.py`:

```python
# encoding=utf-8
import unittest

from game_reverse.actions import validate_action


class TestGameReverseActions(unittest.TestCase):

    def test_accepts_wait_action(self):
        action = validate_action({"type": "wait", "seconds": 2}, ["wait"], (1080, 1920))
        self.assertEqual(action["type"], "wait")
        self.assertEqual(action["seconds"], 2)

    def test_accepts_tap_inside_screen(self):
        action = validate_action({"type": "tap", "x": 100, "y": 200}, ["tap"], (1080, 1920))
        self.assertEqual(action, {"type": "tap", "x": 100, "y": 200})

    def test_rejects_disallowed_action(self):
        with self.assertRaises(ValueError) as ctx:
            validate_action({"type": "shell", "cmd": "pm clear app"}, ["tap"], (1080, 1920))
        self.assertIn("not allowed", str(ctx.exception))

    def test_rejects_out_of_bounds_tap(self):
        with self.assertRaises(ValueError) as ctx:
            validate_action({"type": "tap", "x": 2000, "y": 200}, ["tap"], (1080, 1920))
        self.assertIn("out of bounds", str(ctx.exception))

    def test_rejects_swipe_with_out_of_bounds_point(self):
        with self.assertRaises(ValueError) as ctx:
            validate_action({
                "type": "swipe",
                "x1": 100,
                "y1": 200,
                "x2": 100,
                "y2": 3000,
                "duration": 0.5
            }, ["swipe"], (1080, 1920))
        self.assertIn("out of bounds", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'game_reverse.actions'`.

**Step 3: Write minimal implementation**

Create `game_reverse/actions.py`:

```python
# encoding=utf-8

SAFE_ACTIONS = {"screenshot", "wait", "back", "tap", "swipe"}


def validate_action(action, allowed_actions, screen_size):
    if not isinstance(action, dict):
        raise ValueError("action must be an object")

    action_type = action.get("type")
    if action_type not in SAFE_ACTIONS:
        raise ValueError("action type is not safe")
    if action_type not in allowed_actions:
        raise ValueError("action type is not allowed")

    width, height = screen_size

    if action_type == "screenshot":
        return {"type": "screenshot"}
    if action_type == "back":
        return {"type": "back"}
    if action_type == "wait":
        seconds = action.get("seconds", 1)
        if not isinstance(seconds, (int, float)) or seconds < 0 or seconds > 10:
            raise ValueError("wait seconds must be between 0 and 10")
        return {"type": "wait", "seconds": seconds}
    if action_type == "tap":
        x = action.get("x")
        y = action.get("y")
        _validate_point(x, y, width, height)
        return {"type": "tap", "x": x, "y": y}
    if action_type == "swipe":
        x1 = action.get("x1")
        y1 = action.get("y1")
        x2 = action.get("x2")
        y2 = action.get("y2")
        _validate_point(x1, y1, width, height)
        _validate_point(x2, y2, width, height)
        duration = action.get("duration", 0.5)
        if not isinstance(duration, (int, float)) or duration <= 0 or duration > 5:
            raise ValueError("swipe duration must be between 0 and 5")
        return {"type": "swipe", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration}

    raise ValueError("unsupported action")


def _validate_point(x, y, width, height):
    if not isinstance(x, int) or not isinstance(y, int):
        raise ValueError("coordinates must be integers")
    if x < 0 or y < 0 or x >= width or y >= height:
        raise ValueError("coordinates out of bounds")
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py -v
```

Expected: PASS.

**Step 5: Commit**

Only if the user asked for commits:

```bash
git add game_reverse/actions.py tests/test_game_reverse_actions.py
git commit -m "Add safe action validation"
```

---

## Task 3: Add Journal Writer

**Files:**
- Create: `game_reverse/journal.py`
- Create: `tests/test_game_reverse_journal.py`

**Step 1: Write the failing tests**

Create `tests/test_game_reverse_journal.py`:

```python
# encoding=utf-8
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

            with open(actions_path, "r", encoding="utf-8") as f:
                action = json.loads(f.readline())
            with open(observations_path, "r", encoding="utf-8") as f:
                observation = json.loads(f.readline())

        self.assertEqual(action["result"], "executed")
        self.assertEqual(observation["state"], "main_menu")

    def test_updates_mission_draft(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = Journal.create(tmpdir, session_name="test-session")
            journal.update_mission_draft("# Draft\n\n- Main menu found")
            content = journal.read_mission_draft()

        self.assertIn("Main menu found", content)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'game_reverse.journal'`.

**Step 3: Write minimal implementation**

Create `game_reverse/journal.py`:

```python
# encoding=utf-8
import json
import os
from dataclasses import dataclass


@dataclass
class Journal:
    session_dir: str
    screens_dir: str

    @classmethod
    def create(cls, output_root, session_name):
        session_dir = os.path.join(output_root, session_name)
        screens_dir = os.path.join(session_dir, "screens")
        os.makedirs(screens_dir, exist_ok=True)
        for filename in ("actions.jsonl", "observations.jsonl"):
            path = os.path.join(session_dir, filename)
            if not os.path.exists(path):
                open(path, "a", encoding="utf-8").close()
        draft_path = os.path.join(session_dir, "mission_draft.md")
        if not os.path.exists(draft_path):
            with open(draft_path, "w", encoding="utf-8") as f:
                f.write("# App/Game 探索草稿\n")
        return cls(session_dir=session_dir, screens_dir=screens_dir)

    def screen_path(self, step):
        return os.path.join(self.screens_dir, "step_%04d.png" % step)

    def write_action(self, record):
        self._append_jsonl("actions.jsonl", record)

    def write_observation(self, record):
        self._append_jsonl("observations.jsonl", record)

    def update_mission_draft(self, content):
        with open(os.path.join(self.session_dir, "mission_draft.md"), "w", encoding="utf-8") as f:
            f.write(content)

    def read_mission_draft(self):
        with open(os.path.join(self.session_dir, "mission_draft.md"), "r", encoding="utf-8") as f:
            return f.read()

    def _append_jsonl(self, filename, record):
        with open(os.path.join(self.session_dir, filename), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_game_reverse_journal.py -v
```

Expected: PASS.

**Step 5: Commit**

Only if the user asked for commits:

```bash
git add game_reverse/journal.py tests/test_game_reverse_journal.py
git commit -m "Add explorer journal writer"
```

---

## Task 4: Add Airtest Executor Wrapper

**Files:**
- Create: `game_reverse/airtest_executor.py`
- Create: `tests/test_game_reverse_airtest_executor.py`

**Step 1: Write the failing tests**

Create `tests/test_game_reverse_airtest_executor.py`:

```python
# encoding=utf-8
import unittest

from game_reverse.airtest_executor import AirtestExecutor


class FakeApi:
    def __init__(self):
        self.calls = []

    def snapshot(self, filename=None):
        self.calls.append(("snapshot", filename))
        return filename

    def touch(self, pos):
        self.calls.append(("touch", pos))

    def swipe(self, start, end, duration=0.5):
        self.calls.append(("swipe", start, end, duration))

    def keyevent(self, key):
        self.calls.append(("keyevent", key))

    def sleep(self, seconds):
        self.calls.append(("sleep", seconds))


class TestAirtestExecutor(unittest.TestCase):

    def test_executes_screenshot(self):
        api = FakeApi()
        executor = AirtestExecutor(api=api)
        executor.execute({"type": "screenshot"}, screen_path="screen.png")
        self.assertEqual(api.calls, [("snapshot", "screen.png")])

    def test_executes_tap(self):
        api = FakeApi()
        executor = AirtestExecutor(api=api)
        executor.execute({"type": "tap", "x": 10, "y": 20}, screen_path="screen.png")
        self.assertEqual(api.calls, [("touch", (10, 20))])

    def test_executes_back(self):
        api = FakeApi()
        executor = AirtestExecutor(api=api)
        executor.execute({"type": "back"}, screen_path="screen.png")
        self.assertEqual(api.calls, [("keyevent", "BACK")])


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_game_reverse_airtest_executor.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'game_reverse.airtest_executor'`.

**Step 3: Write minimal implementation**

Create `game_reverse/airtest_executor.py`:

```python
# encoding=utf-8
from airtest.core import api as airtest_api


class AirtestExecutor:
    def __init__(self, api=None):
        self.api = api or airtest_api

    def connect(self, device_uri):
        return self.api.connect_device(device_uri)

    def start_app(self, package_name):
        return self.api.start_app(package_name)

    def execute(self, action, screen_path):
        action_type = action["type"]
        if action_type == "screenshot":
            self.api.snapshot(filename=screen_path)
            return "executed"
        if action_type == "tap":
            self.api.touch((action["x"], action["y"]))
            return "executed"
        if action_type == "swipe":
            self.api.swipe(
                (action["x1"], action["y1"]),
                (action["x2"], action["y2"]),
                duration=action.get("duration", 0.5),
            )
            return "executed"
        if action_type == "back":
            self.api.keyevent("BACK")
            return "executed"
        if action_type == "wait":
            self.api.sleep(action.get("seconds", 1))
            return "executed"
        raise ValueError("unsupported action")
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_game_reverse_airtest_executor.py -v
```

Expected: PASS.

**Step 5: Commit**

Only if the user asked for commits:

```bash
git add game_reverse/airtest_executor.py tests/test_game_reverse_airtest_executor.py
git commit -m "Add Airtest safe action executor"
```

---

## Task 5: Add Claude Decision Parser and Client Boundary

**Files:**
- Create: `game_reverse/llm_decider.py`
- Create: `tests/test_game_reverse_llm_decider.py`

**Step 1: Write the failing tests**

Create `tests/test_game_reverse_llm_decider.py`:

```python
# encoding=utf-8
import unittest

from game_reverse.llm_decider import parse_decision


class TestLLMDecider(unittest.TestCase):

    def test_parses_valid_decision(self):
        decision = parse_decision('''{
          "screen_summary": "主界面",
          "state": "main_menu",
          "action": {"type": "wait", "seconds": 1},
          "reason": "观察界面",
          "new_findings": [],
          "screenshot_tags": [],
          "risks": []
        }''')

        self.assertEqual(decision["state"], "main_menu")
        self.assertEqual(decision["action"]["type"], "wait")

    def test_rejects_missing_action(self):
        with self.assertRaises(ValueError) as ctx:
            parse_decision('{"screen_summary": "主界面", "state": "main_menu"}')
        self.assertIn("action", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_game_reverse_llm_decider.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'game_reverse.llm_decider'`.

**Step 3: Write minimal implementation**

Create `game_reverse/llm_decider.py`:

```python
# encoding=utf-8
import base64
import json


REQUIRED_DECISION_FIELDS = [
    "screen_summary", "state", "action", "reason", "new_findings", "screenshot_tags", "risks"
]


def parse_decision(text):
    try:
        decision = json.loads(text)
    except ValueError as exc:
        raise ValueError("Claude decision must be valid JSON") from exc

    for field in REQUIRED_DECISION_FIELDS:
        if field not in decision:
            raise ValueError("Claude decision missing %s" % field)
    if not isinstance(decision["action"], dict):
        raise ValueError("Claude decision action must be an object")
    return decision


class ClaudeDecider:
    def __init__(self, model):
        self.model = model

    def decide(self, screen_path, mission, recent_actions, mission_draft):
        client = _create_anthropic_client()
        with open(screen_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": _build_decision_prompt(mission, recent_actions, mission_draft),
                    },
                ],
            }],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": _decision_schema(),
                }
            },
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        return parse_decision(text)


def _create_anthropic_client():
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("Install the optional dependency with: pip install anthropic") from exc
    return anthropic.Anthropic()


def _build_decision_prompt(mission, recent_actions, mission_draft):
    return """你正在黑盒探索一个 Android App/Game，用于授权测试、功能验证或设计逆向分析。
只允许建议 screenshot、wait、back、tap、swipe 中的动作。
遇到登录、实名、支付、权限授权、账号密码输入等敏感界面时，建议 back 或 wait。

Mission 类型：%s
Mission 目标：%s
Mission 关注目标：%s
Mission 成功标准：%s

最近动作：
%s

当前任务草稿：
%s

请根据截图输出下一步动作和新发现。""" % (
        mission.type,
        mission.goal,
        json.dumps(mission.targets, ensure_ascii=False),
        json.dumps(mission.success_criteria, ensure_ascii=False),
        json.dumps(recent_actions, ensure_ascii=False),
        mission_draft,
    )


def _decision_schema():
    return {
        "type": "object",
        "properties": {
            "screen_summary": {"type": "string"},
            "state": {"type": "string"},
            "action": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["screenshot", "wait", "back", "tap", "swipe"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "x1": {"type": "integer"},
                    "y1": {"type": "integer"},
                    "x2": {"type": "integer"},
                    "y2": {"type": "integer"},
                    "seconds": {"type": "number"},
                    "duration": {"type": "number"}
                },
                "required": ["type"],
                "additionalProperties": False
            },
            "reason": {"type": "string"},
            "new_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "claim": {"type": "string"},
                        "evidence": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]}
                    },
                    "required": ["category", "claim", "evidence", "confidence"],
                    "additionalProperties": False
                }
            },
            "screenshot_tags": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}}
        },
        "required": REQUIRED_DECISION_FIELDS,
        "additionalProperties": False
    }
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_game_reverse_llm_decider.py -v
```

Expected: PASS.

**Step 5: Commit**

Only if the user asked for commits:

```bash
git add game_reverse/llm_decider.py tests/test_game_reverse_llm_decider.py
git commit -m "Add mission-aware Claude decision parser"
```

---

## Task 6: Add Mission Draft Updater and Final Report Writer

**Files:**
- Create: `game_reverse/report_writer.py`
- Create: `tests/test_game_reverse_report_writer.py`

**Step 1: Write the failing tests**

Create `tests/test_game_reverse_report_writer.py`:

```python
# encoding=utf-8
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
            "new_findings": [{
                "category": "任务系统",
                "claim": "主界面存在任务入口",
                "evidence": "screens/step_0001.png",
                "confidence": "medium"
            }],
            "risks": []
        }

        result = update_mission_draft(draft, step=1, decision=decision)

        self.assertIn("任务系统", result)
        self.assertIn("主界面存在任务入口", result)
        self.assertIn("screens/step_0001.png", result)

    def test_write_feature_test_report_mentions_coverage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            observations_path = os.path.join(tmpdir, "observations.jsonl")
            with open(observations_path, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "step": 1,
                    "mission_type": "feature_test",
                    "state": "main_menu",
                    "screen_summary": "主界面"
                }, ensure_ascii=False) + "\n")

            mission = Mission(type="feature_test", goal="测试任务入口", targets=["任务"])
            write_final_report(tmpdir, "# 草稿", mission, stop_reason="max_steps_reached")

            with open(os.path.join(tmpdir, "final_report.md"), "r", encoding="utf-8") as f:
                report = f.read()

        self.assertIn("功能测试阶段报告", report)
        self.assertIn("任务", report)
        self.assertIn("main_menu", report)

    def test_write_level_design_report_mentions_level_analysis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "observations.jsonl"), "w", encoding="utf-8").close()
            mission = Mission(type="level_design_reverse", goal="逆推关卡", targets=["关卡列表"])
            write_final_report(tmpdir, "# 草稿", mission, stop_reason="max_steps_reached")

            with open(os.path.join(tmpdir, "final_report.md"), "r", encoding="utf-8") as f:
                report = f.read()

        self.assertIn("关卡设计逆推报告", report)
        self.assertIn("关卡列表", report)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_game_reverse_report_writer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'game_reverse.report_writer'`.

**Step 3: Write minimal implementation**

Create `game_reverse/report_writer.py`:

```python
# encoding=utf-8
import json
import os
from collections import Counter


def update_mission_draft(current_draft, step, decision):
    lines = [current_draft.rstrip(), "", "## Step %04d 新发现" % step]
    for finding in decision.get("new_findings", []):
        lines.append("- **%s**：%s" % (finding["category"], finding["claim"]))
        lines.append("  - 证据：%s" % finding["evidence"])
        lines.append("  - 置信度：%s" % finding["confidence"])
    if decision.get("risks"):
        lines.append("- 风险：%s" % "；".join(decision["risks"]))
    lines.append("")
    return "\n".join(lines)


def write_final_report(session_dir, mission_draft, mission, stop_reason):
    states = _load_state_counts(session_dir)
    title = _report_title(mission.type)
    sections = [
        "# %s" % title,
        "",
        "## Mission",
        "",
        "- 类型：%s" % mission.type,
        "- 目标：%s" % mission.goal,
        "- 关注对象：%s" % ("、".join(mission.targets) if mission.targets else "无指定目标"),
        "",
        "## 停止原因",
        "",
        stop_reason,
        "",
        "## 状态覆盖",
        "",
    ]
    for state, count in states.most_common():
        sections.append("- %s：%s 次" % (state, count))
    sections.extend(_mission_sections(mission.type))
    sections.extend(["", "## 任务草稿", "", mission_draft])

    with open(os.path.join(session_dir, "final_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(sections))


def _load_state_counts(session_dir):
    observations_path = os.path.join(session_dir, "observations.jsonl")
    states = Counter()
    if os.path.exists(observations_path):
        with open(observations_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    observation = json.loads(line)
                    states[observation.get("state", "unknown")] += 1
    return states


def _report_title(mission_type):
    if mission_type == "feature_test":
        return "App/Game 功能测试阶段报告"
    if mission_type == "level_design_reverse":
        return "关卡设计逆推报告"
    return "App/Game 自由探索报告"


def _mission_sections(mission_type):
    if mission_type == "feature_test":
        return ["", "## 功能覆盖", "", "## 失败或卡住步骤", "", "## 可疑 Bug", ""]
    if mission_type == "level_design_reverse":
        return ["", "## 关卡入口与路径", "", "## 关卡列表结构", "", "## 奖励与解锁条件", "", "## 难度递进推测", ""]
    return ["", "## 功能地图", "", "## 可疑入口", "", "## 下一轮探索建议", ""]
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_game_reverse_report_writer.py -v
```

Expected: PASS.

**Step 5: Commit**

Only if the user asked for commits:

```bash
git add game_reverse/report_writer.py tests/test_game_reverse_report_writer.py
git commit -m "Add mission-specific report writer"
```

---

## Task 7: Add Main Loop Orchestrator

**Files:**
- Create: `game_reverse/run_loop.py`
- Create: `tests/test_game_reverse_run_loop.py`

**Step 1: Write the failing test**

Create `tests/test_game_reverse_run_loop.py`:

```python
# encoding=utf-8
import os
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
            with open(screen_path, "wb") as f:
                f.write(b"fake png")
        return "executed"


class FakeDecider:
    def decide(self, screen_path, mission, recent_actions, mission_draft):
        return {
            "screen_summary": "主界面",
            "state": "main_menu",
            "action": {"type": "wait", "seconds": 1},
            "reason": "等待观察",
            "new_findings": [{
                "category": "主界面",
                "claim": "发现主界面",
                "evidence": screen_path,
                "confidence": "high"
            }],
            "screenshot_tags": ["主界面"],
            "risks": []
        }


class TestRunLoop(unittest.TestCase):

    def test_runs_fixed_number_of_steps_with_mission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameReverseConfig(
                device_uri="Android:///",
                package_name="com.example.game",
                max_steps=2,
                output_root=tmpdir,
                allowed_actions=["screenshot", "wait"],
                mission=Mission(type="feature_test", goal="测试任务", targets=["任务"])
            )
            executor = FakeExecutor()
            session_dir = run_loop(config, executor=executor, decider=FakeDecider(), session_name="test-session")

            self.assertTrue(os.path.exists(os.path.join(session_dir, "actions.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "observations.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "mission_draft.md")))
            self.assertTrue(os.path.exists(os.path.join(session_dir, "final_report.md")))
            self.assertEqual(len([call for call in executor.executed if call[0]["type"] == "wait"]), 2)

            with open(os.path.join(session_dir, "final_report.md"), "r", encoding="utf-8") as f:
                report = f.read()
            self.assertIn("功能测试阶段报告", report)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_game_reverse_run_loop.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'game_reverse.run_loop'`.

**Step 3: Write minimal implementation**

Create `game_reverse/run_loop.py`:

```python
# encoding=utf-8
import argparse
import os
import time

from game_reverse.actions import validate_action
from game_reverse.airtest_executor import AirtestExecutor
from game_reverse.config import load_config
from game_reverse.journal import Journal
from game_reverse.llm_decider import ClaudeDecider
from game_reverse.report_writer import update_mission_draft, write_final_report


def run_loop(config, executor=None, decider=None, session_name=None):
    executor = executor or AirtestExecutor()
    decider = decider or ClaudeDecider(config.model)
    session_name = session_name or time.strftime("%Y%m%d-%H%M%S")
    journal = Journal.create(config.output_root, session_name)

    executor.connect(config.device_uri)
    executor.start_app(config.package_name)

    recent_actions = []
    failure_count = 0
    stop_reason = "max_steps_reached"

    for step in range(1, config.max_steps + 1):
        screen_path = journal.screen_path(step)
        try:
            executor.execute({"type": "screenshot"}, screen_path)
            screen_size = _read_screen_size(screen_path)
            mission_draft = journal.read_mission_draft()
            decision = decider.decide(screen_path, config.mission, recent_actions[-config.recent_steps:], mission_draft)
            action = validate_action(decision["action"], config.allowed_actions, screen_size)
            result = executor.execute(action, screen_path)

            action_record = {
                "step": step,
                "screen": os.path.relpath(screen_path, journal.session_dir),
                "mission_type": config.mission.type,
                "action": action,
                "reason": decision.get("reason", ""),
                "result": result,
            }
            observation_record = {
                "step": step,
                "mission_type": config.mission.type,
                "state": decision.get("state", "unknown"),
                "screen_summary": decision.get("screen_summary", ""),
                "findings": decision.get("new_findings", []),
                "screenshot_tags": decision.get("screenshot_tags", []),
                "risks": decision.get("risks", []),
            }
            journal.write_action(action_record)
            journal.write_observation(observation_record)
            journal.update_mission_draft(update_mission_draft(mission_draft, step, decision))
            recent_actions.append(action_record)
            failure_count = 0
        except Exception as exc:
            failure_count += 1
            journal.write_action({
                "step": step,
                "screen": os.path.relpath(screen_path, journal.session_dir),
                "mission_type": config.mission.type,
                "action": {"type": "error"},
                "reason": str(exc),
                "result": "failed",
            })
            if failure_count >= config.consecutive_failure_limit:
                stop_reason = "consecutive_failures"
                break

    write_final_report(journal.session_dir, journal.read_mission_draft(), config.mission, stop_reason)
    return journal.session_dir


def _read_screen_size(screen_path):
    try:
        from PIL import Image
        with Image.open(screen_path) as image:
            return image.size
    except Exception:
        return (1080, 1920)


def main():
    parser = argparse.ArgumentParser(description="Run Claude-guided Airtest App/Game exploration.")
    parser.add_argument("--config", required=True, help="Path to game_reverse config JSON")
    args = parser.parse_args()
    config = load_config(args.config)
    session_dir = run_loop(config)
    print("Session written to: %s" % session_dir)


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_game_reverse_run_loop.py -v
```

Expected: PASS.

**Step 5: Commit**

Only if the user asked for commits:

```bash
git add game_reverse/run_loop.py tests/test_game_reverse_run_loop.py
git commit -m "Add mission-driven exploration loop"
```

---

## Task 8: Add Prompt and Report Template Files

**Files:**
- Create: `game_reverse/prompts/decision_system.md`
- Create: `game_reverse/prompts/report_templates/free_explore.md`
- Create: `game_reverse/prompts/report_templates/feature_test.md`
- Create: `game_reverse/prompts/report_templates/level_design_reverse.md`

**Step 1: Create decision prompt**

Create `game_reverse/prompts/decision_system.md`:

```markdown
你是一个 App/Game 黑盒测试与设计分析代理。

目标：基于当前截图、mission 和历史动作，选择下一步安全探索动作，并增量记录对本次 mission 有价值的新发现。

只允许建议这些动作：

- screenshot
- wait
- back
- tap
- swipe

禁止建议：

- 购买、充值、支付确认
- 安装、卸载、清数据
- 修改系统设置
- 输入账号、密码、手机号、验证码
- 任意 shell 或 ADB 命令

遇到登录、实名、支付、权限授权、账号密码输入等敏感界面时，建议 back 或 wait。

输出必须是符合本地 JSON schema 的 JSON，不要输出 Markdown。
```

**Step 2: Create report templates**

Create `game_reverse/prompts/report_templates/free_explore.md`:

```markdown
# App/Game 自由探索报告

## Mission
## 状态覆盖
## 功能地图
## 可疑入口
## 截图证据索引
## 不确定点
## 下一轮探索建议
```

Create `game_reverse/prompts/report_templates/feature_test.md`:

```markdown
# App/Game 功能测试阶段报告

## Mission
## 目标功能覆盖
## 每个功能入口截图
## 失败或卡住步骤
## 可疑 Bug
## 未覆盖功能
## 下一轮测试建议
```

Create `game_reverse/prompts/report_templates/level_design_reverse.md`:

```markdown
# 关卡设计逆推报告

## Mission
## 关卡入口与路径
## 关卡列表结构
## 关卡详情字段
## 解锁条件
## 奖励结构
## 难度递进推测
## 截图证据索引
## 不确定点
```

**Step 3: Run all new tests**

Run:

```bash
python -m pytest tests/test_game_reverse_mission.py tests/test_game_reverse_config.py tests/test_game_reverse_actions.py tests/test_game_reverse_journal.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py -v
```

Expected: PASS.

**Step 4: Commit**

Only if the user asked for commits:

```bash
git add game_reverse/prompts/decision_system.md game_reverse/prompts/report_templates/free_explore.md game_reverse/prompts/report_templates/feature_test.md game_reverse/prompts/report_templates/level_design_reverse.md
git commit -m "Add explorer prompt templates"
```

---

## Task 9: Manual Smoke Test on Android Emulator

**Files:**
- No code changes expected.
- Runtime config: create a local config file outside git or copy `game_reverse/config.example.json` to a user-specific path.

**Step 1: Verify emulator is visible**

Run:

```bash
adb devices
```

Expected: at least one device in `device` state, such as `127.0.0.1:7555 device` or `emulator-5554 device`.

**Step 2: Find package name if needed**

Run:

```bash
adb shell pm list packages
```

Expected: output includes the target package, for example `package:com.example.game`.

If the app is already open, inspect foreground activity:

```bash
adb shell dumpsys window
```

Expected: output contains the current package/activity. Search manually in the terminal output if needed.

**Step 3: Create local no-click config**

Create a local untracked config, for example `game_reverse/local.config.json`:

```json
{
  "device_uri": "Android:///",
  "package_name": "com.example.game",
  "max_steps": 1,
  "model": "claude-opus-4-8",
  "allowed_actions": ["screenshot", "wait", "back"],
  "mission": {
    "type": "free_explore",
    "goal": "自由探索 App/Game 并总结界面与功能",
    "targets": [],
    "success_criteria": []
  }
}
```

Do not commit `game_reverse/local.config.json` if it contains target-app details the user considers private.

**Step 4: Run one-step no-click smoke test**

Run:

```bash
python -m game_reverse.run_loop --config game_reverse/local.config.json
```

Expected:

- A session directory is printed.
- `screens/step_0001.png` exists.
- `actions.jsonl` exists.
- `observations.jsonl` exists.
- `mission_draft.md` exists.
- `final_report.md` exists.

**Step 5: Inspect outputs**

Open the printed session directory and verify:

- The screenshot is the emulator screen.
- The action is only `wait` or `back` in no-click mode.
- The mission draft contains evidence-backed findings.
- No sensitive action was executed.

---

## Task 10: Run Mission-Specific Explorations

**Files:**
- No code changes expected if prior tasks are complete.
- Runtime config only.

**Step 1: Configure `feature_test`**

Use this local config when testing app features:

```json
{
  "device_uri": "Android:///",
  "package_name": "com.example.game",
  "max_steps": 10,
  "model": "claude-opus-4-8",
  "allowed_actions": ["screenshot", "wait", "back", "tap", "swipe"],
  "mission": {
    "type": "feature_test",
    "goal": "测试首页、任务、背包、商店四个入口是否可进入，并保存截图",
    "targets": ["首页", "任务", "背包", "商店"],
    "success_criteria": [
      "每个目标功能至少进入一次",
      "每个目标功能保存一张截图",
      "遇到登录、支付、实名页面停止并标记人工处理"
    ]
  }
}
```

Run:

```bash
python -m game_reverse.run_loop --config game_reverse/local.config.json
```

Expected: `final_report.md` is a 功能测试阶段报告 and mentions target coverage.

**Step 2: Configure `level_design_reverse`**

Use this local config when reverse-engineering level design:

```json
{
  "device_uri": "Android:///",
  "package_name": "com.example.game",
  "max_steps": 20,
  "model": "claude-opus-4-8",
  "allowed_actions": ["screenshot", "wait", "back", "tap", "swipe"],
  "mission": {
    "type": "level_design_reverse",
    "goal": "探索关卡入口、关卡列表、解锁条件、奖励、难度变化，并截图保存",
    "targets": ["关卡入口", "关卡列表", "关卡详情", "胜利结算", "失败结算"],
    "success_criteria": [
      "保存关卡列表截图",
      "保存至少 3 个关卡详情截图",
      "记录关卡名称、消耗、推荐战力、奖励、解锁条件",
      "输出关卡设计规律推测"
    ]
  }
}
```

Run:

```bash
python -m game_reverse.run_loop --config game_reverse/local.config.json
```

Expected: `final_report.md` is a 关卡设计逆推报告 and includes level-design sections.

**Step 3: Review logs**

Inspect `actions.jsonl` and `observations.jsonl`.

Expected:

- Every action has a reason.
- Every finding has evidence and confidence.
- Screenshot paths match real files.
- Unsafe actions are not present.

**Step 4: Commit if this test required code fixes**

Only if code was changed and user asked for commits:

```bash
git add game_reverse tests
git commit -m "Stabilize mission-driven app explorer"
```

---

## Final Verification Checklist

Run unit tests:

```bash
python -m pytest tests/test_game_reverse_mission.py tests/test_game_reverse_config.py tests/test_game_reverse_actions.py tests/test_game_reverse_journal.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py -v
```

Expected: all new tests PASS.

Run no-click smoke test on emulator:

```bash
python -m game_reverse.run_loop --config game_reverse/local.config.json
```

Expected: session outputs are created and no unsafe action is executed.

Run limited tap/swipe tests only after reviewing no-click outputs.

---

## Notes for the Implementer

- Keep `anthropic` as an optional runtime dependency unless the project owner wants it added to repository requirements.
- Do not hard-code package names, API keys, account data, or target-app details.
- Do not use arbitrary `adb shell` as part of the automated loop.
- Keep tests fake-based and deterministic; real emulator tests are manual smoke tests.
- If Claude outputs an unsafe action, the local validator must win.
- `game_reverse/` remains the first-version package directory, but its product semantics are mission-driven App/Game exploration.
- If the implementation diverges from `docs/plans/2026-06-16-game-reverse-design.md`, update the design doc in a separate explicit task.
