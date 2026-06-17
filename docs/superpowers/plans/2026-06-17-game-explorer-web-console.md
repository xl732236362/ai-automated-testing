# Game Explorer Web Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first static Chinese Web console for configuring and observing App/Game exploration tasks.

**Architecture:** The first phase is plain static web assets under `web/`, backed by `web/data/sample-run.json`. Python unit tests validate file presence, data shape, and key UI integration points. No backend, command execution, device connection, or secret handling is added in this phase.

**Tech Stack:** HTML, CSS, vanilla JavaScript, JSON sample data, Python `unittest`.

---

## File Structure

- Create `web/index.html`: Chinese operator console shell and semantic UI regions.
- Create `web/styles.css`: responsive operations-console styling.
- Create `web/app.js`: load sample JSON, render mission fields, runners, timeline, risks, and outputs.
- Create `web/data/sample-run.json`: static sample shaped like `game_reverse` config/action/observation records.
- Create `tests/test_web_console_static.py`: lightweight static file and JSON structure tests.

## Task 1: Static Asset Contract Tests

**Files:**
- Create: `tests/test_web_console_static.py`

- [ ] **Step 1: Write the failing static contract tests**

Create `tests/test_web_console_static.py` with tests that assert:

```python
# -*- coding: utf-8 -*-
"""Tests for the static game explorer web console."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"


class TestWebConsoleStatic(unittest.TestCase):
    def test_static_files_exist(self):
        expected_files = [
            WEB_DIR / "index.html",
            WEB_DIR / "styles.css",
            WEB_DIR / "app.js",
            WEB_DIR / "data" / "sample-run.json",
        ]

        for path in expected_files:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), "%s should exist" % path)

    def test_index_wires_assets_and_sample_data(self):
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

        self.assertIn('lang="zh-CN"', html)
        self.assertIn('href="styles.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertIn('data-sample-url="data/sample-run.json"', html)
        self.assertIn("App/Game 探索控制台", html)

    def test_sample_run_json_has_required_shape(self):
        data = json.loads((WEB_DIR / "data" / "sample-run.json").read_text(encoding="utf-8"))

        self.assertEqual(data["config"]["device_uri"], "Android:///emulator-5554")
        self.assertEqual(data["config"]["package_name"], "com.example.game")
        self.assertIn(data["config"]["mission"]["type"], ["free_explore", "feature_test", "level_design_reverse"])
        self.assertIn("codex_exec", [runner["id"] for runner in data["runners"]])
        self.assertIn("claude_print", [runner["id"] for runner in data["runners"]])
        self.assertGreaterEqual(len(data["run"]["steps"]), 3)
        self.assertIn("session_dir", data["run"]["outputs"])
        self.assertIn("final_report", data["run"]["outputs"])

    def test_app_declares_static_only_boundary(self):
        script = (WEB_DIR / "app.js").read_text(encoding="utf-8")

        self.assertIn("STATIC_ONLY", script)
        self.assertIn("fetch(sampleUrl)", script)
        self.assertNotIn("child_process", script)
        self.assertNotIn("codex exec", script)
        self.assertNotIn("claude -p", script)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: fail because `web/index.html` and related static files do not exist.

## Task 2: Static Sample Data

**Files:**
- Create: `web/data/sample-run.json`

- [ ] **Step 1: Create sample data**

Create `web/data/sample-run.json` with config, runner metadata, run steps, risks, outputs, and report preview text. Include three runner IDs: `game_reverse`, `codex_exec`, and `claude_print`.

- [ ] **Step 2: Run the web static tests**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: still fail because HTML, CSS, and JS do not exist yet.

## Task 3: HTML Shell

**Files:**
- Create: `web/index.html`

- [ ] **Step 1: Create the Chinese console HTML**

Create a semantic page with:

- `<html lang="zh-CN">`
- `<meta charset="utf-8">`
- `<link rel="stylesheet" href="styles.css">`
- `<main id="app" data-sample-url="data/sample-run.json">`
- left navigation, mission configuration region, timeline region, and right inspector region
- `<script src="app.js"></script>`

- [ ] **Step 2: Run the web static tests**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: still fail because `styles.css` and `app.js` do not exist yet.

## Task 4: Styling And Rendering

**Files:**
- Create: `web/styles.css`
- Create: `web/app.js`

- [ ] **Step 1: Create console styling**

Create a responsive, dense operations-console CSS layout with:

- three-column desktop layout
- one-column mobile layout
- stable panels, inputs, segmented runner/action controls, timeline rows, screenshot preview, risk list, and report preview
- restrained neutral colors with limited accent usage

- [ ] **Step 2: Create vanilla JS renderer**

Create `web/app.js` that:

- defines `const STATIC_ONLY = true`
- reads `data-sample-url` from `#app`
- calls `fetch(sampleUrl)`
- renders config fields, runner choices, allowed actions, timeline, risks, outputs, and report preview from JSON
- marks backend execution controls as planned integrations rather than live command execution

- [ ] **Step 3: Run tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: all tests pass.

## Task 5: Browser Verification And Commit

**Files:**
- Verify: `web/index.html`
- Modify if needed: `web/styles.css`, `web/app.js`

- [ ] **Step 1: Open the static console in a browser**

Use a local file or localhost server to inspect `web/index.html`.

- [ ] **Step 2: Verify visible requirements**

Confirm:

- Page opens directly into the console.
- UI is Chinese.
- Mission config, runner selector, decision timeline, screenshot preview, risks, and output paths are visible.
- Buttons do not imply live backend execution.

- [ ] **Step 3: Run final verification**

Run:

```bash
python -m unittest tests.test_web_console_static tests.test_game_reverse_actions tests.test_game_reverse_airtest_executor tests.test_game_reverse_config tests.test_game_reverse_journal tests.test_game_reverse_llm_decider tests.test_game_reverse_mission tests.test_game_reverse_report_writer tests.test_game_reverse_run_loop
```

Expected: all listed tests pass.

- [ ] **Step 4: Commit implementation**

Commit:

```bash
git add web tests/test_web_console_static.py docs/superpowers/plans/2026-06-17-game-explorer-web-console.md
git commit -m "Add static game explorer web console"
```
