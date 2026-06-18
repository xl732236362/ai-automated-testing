# Smart Target Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only smart target configuration so the Web UI can detect Android devices, use the current foreground app as `package_name`, and validate the configured package before a run.

**Architecture:** Add a focused `game_reverse.target_discovery` module for ADB command resolution, output parsing, and safe identifier validation. Expose discovery through `GameReverseWebService` and `game_reverse.web_server` as fixed JSON endpoints, then wire compact controls into the existing Web task configuration panel.

**Tech Stack:** Python standard library `unittest`, `subprocess`, existing `ThreadingHTTPServer`, vanilla JavaScript, static HTML/CSS, `node --check`.

---

## File Structure

- Create `game_reverse/target_discovery.py`: read-only ADB discovery boundary, parser functions, subprocess runner, and JSON-friendly result dictionaries.
- Create `tests/test_game_reverse_target_discovery.py`: unit tests for parsing, validation, command construction, and fake runner behavior.
- Modify `game_reverse/web_service.py`: compose a target discovery object and expose `list_devices`, `foreground_app`, and `package_validation`.
- Modify `tests/test_game_reverse_web_service.py`: service-level tests using a fake discovery object.
- Modify `game_reverse/web_server.py`: route fixed discovery endpoints.
- Modify `tests/test_game_reverse_web_server.py`: HTTP route tests for discovery JSON and error status.
- Modify `web/index.html`: add smart config controls/status under the existing task fields.
- Modify `web/app.js`: call discovery endpoints, fill fields, and render status without changing run safety.
- Modify `web/styles.css`: add compact smart config control/status styles.
- Modify `tests/test_web_console_static.py`: static tests for controls, endpoint references, and readable Chinese.
- Modify this plan file as tasks are executed, marking only completed steps as `[x]`.

## Task 1: Target Discovery Tests

**Files:**
- Create: `tests/test_game_reverse_target_discovery.py`

- [x] **Step 1: Create failing parser and validation tests**

Create `tests/test_game_reverse_target_discovery.py` with:

```python
# -*- coding: utf-8 -*-
"""Tests for read-only Android target discovery."""

import unittest

from game_reverse.target_discovery import (
    TargetDiscoveryError,
    parse_adb_devices,
    parse_foreground_app,
    parse_package_validation,
    validate_device_id,
    validate_package_name,
)


class TestTargetDiscoveryParsing(unittest.TestCase):
    def test_parse_adb_devices_returns_only_online_devices(self):
        output = """List of devices attached
emulator-5554\tdevice
offline-1\toffline
ABC123\tdevice product:test model:Pixel_7 device:panther

"""

        devices = parse_adb_devices(output)

        self.assertEqual(
            devices,
            [
                {
                    "id": "emulator-5554",
                    "uri": "Android:///emulator-5554",
                    "status": "device",
                    "label": "emulator-5554",
                },
                {
                    "id": "ABC123",
                    "uri": "Android:///ABC123",
                    "status": "device",
                    "label": "ABC123",
                },
            ],
        )

    def test_parse_adb_devices_returns_empty_list_for_no_online_devices(self):
        output = "List of devices attached\nemulator-5554\toffline\n"

        self.assertEqual(parse_adb_devices(output), [])

    def test_parse_foreground_app_prefers_activity_top_resumed(self):
        output = (
            "topResumedActivity=ActivityRecord{67a175a u0 "
            "com.redlinegames.matchsniper3d/com.unity3d.player.UnityPlayerActivity t57}\n"
        )

        result = parse_foreground_app(output, source="dumpsys activity activities")

        self.assertEqual(result["package_name"], "com.redlinegames.matchsniper3d")
        self.assertEqual(result["activity"], "com.unity3d.player.UnityPlayerActivity")
        self.assertEqual(result["source"], "dumpsys activity activities")

    def test_parse_foreground_app_supports_window_focus(self):
        output = (
            "mCurrentFocus=Window{549c6d3 u0 "
            "com.redlinegames.matchsniper3d/com.unity3d.player.UnityPlayerActivity}\n"
        )

        result = parse_foreground_app(output, source="dumpsys window")

        self.assertEqual(result["package_name"], "com.redlinegames.matchsniper3d")
        self.assertEqual(result["activity"], "com.unity3d.player.UnityPlayerActivity")

    def test_parse_foreground_app_rejects_missing_focus(self):
        with self.assertRaisesRegex(TargetDiscoveryError, "foreground app"):
            parse_foreground_app("no focused activity here", source="dumpsys window")

    def test_parse_package_validation_detects_launchable_package(self):
        output = (
            "package:com.redlinegames.matchsniper3d\n"
            "com.redlinegames.matchsniper3d/com.unity3d.player.UnityPlayerActivity\n"
        )

        result = parse_package_validation(
            "emulator-5554",
            "com.redlinegames.matchsniper3d",
            package_output=output,
            resolve_output="com.redlinegames.matchsniper3d/com.unity3d.player.UnityPlayerActivity\n",
        )

        self.assertEqual(
            result,
            {
                "device_id": "emulator-5554",
                "package_name": "com.redlinegames.matchsniper3d",
                "installed": True,
                "launchable": True,
                "activity": "com.unity3d.player.UnityPlayerActivity",
                "warnings": [],
            },
        )

    def test_parse_package_validation_reports_missing_package(self):
        result = parse_package_validation(
            "emulator-5554",
            "com.example.missing",
            package_output="",
            resolve_output="No activity found\n",
        )

        self.assertFalse(result["installed"])
        self.assertFalse(result["launchable"])
        self.assertEqual(result["warnings"], ["包名未安装"])

    def test_validate_device_id_rejects_shell_fragments(self):
        for value in ["", "emulator 5554", "emulator-5554;rm", "../device", "a|b"]:
            with self.subTest(value=value):
                with self.assertRaises(TargetDiscoveryError):
                    validate_device_id(value)

    def test_validate_package_name_rejects_unsafe_values(self):
        for value in ["", "com example", "com.example;rm", "../pkg", "com.example/$"]:
            with self.subTest(value=value):
                with self.assertRaises(TargetDiscoveryError):
                    validate_package_name(value)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_game_reverse_target_discovery
```

Expected: fail with `ModuleNotFoundError: No module named 'game_reverse.target_discovery'`.

## Task 2: Target Discovery Module

**Files:**
- Create: `game_reverse/target_discovery.py`
- Modify: `tests/test_game_reverse_target_discovery.py`

- [x] **Step 1: Implement minimal parsing and validation module**

Create `game_reverse/target_discovery.py`:

```python
# -*- coding: utf-8 -*-
"""Read-only Android target discovery for the Web console."""

import os
import re
import shutil
import subprocess


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED_WINDOWS_ADB = os.path.join(
    PROJECT_ROOT,
    "airtest",
    "core",
    "android",
    "static",
    "adb",
    "windows",
    "adb.exe",
)
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
PACKAGE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$")
FOREGROUND_PATTERNS = [
    re.compile(r"topResumedActivity=.*?\s([A-Za-z0-9_.$]+)/([A-Za-z0-9_.$]+)"),
    re.compile(r"mResumedActivity=.*?\s([A-Za-z0-9_.$]+)/([A-Za-z0-9_.$]+)"),
    re.compile(r"mCurrentFocus=.*?\s([A-Za-z0-9_.$]+)/([A-Za-z0-9_.$]+)"),
    re.compile(r"mFocusedApp=.*?\s([A-Za-z0-9_.$]+)/([A-Za-z0-9_.$]+)"),
]


class TargetDiscoveryError(ValueError):
    """Raised when target discovery cannot produce a safe result."""


class AdbRunner:
    def __init__(self, adb_path=None, timeout=8):
        self.adb_path = adb_path or resolve_adb_path()
        self.timeout = timeout

    def run(self, args):
        command = [self.adb_path] + list(args)
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                check=False,
            )
        except OSError as exc:
            raise TargetDiscoveryError("adb command failed: %s" % exc) from exc
        except subprocess.TimeoutExpired as exc:
            raise TargetDiscoveryError("adb command timed out") from exc
        return (completed.stdout or "") + (completed.stderr or "")


class TargetDiscovery:
    def __init__(self, adb_runner=None):
        self.adb_runner = adb_runner

    def list_devices(self):
        return parse_adb_devices(self._runner().run(["devices"]))

    def foreground_app(self, device_id):
        device_id = validate_device_id(device_id)
        activities_output = self._runner().run(
            ["-s", device_id, "shell", "dumpsys", "activity", "activities"]
        )
        try:
            result = parse_foreground_app(activities_output, "dumpsys activity activities")
        except TargetDiscoveryError:
            window_output = self._runner().run(["-s", device_id, "shell", "dumpsys", "window"])
            result = parse_foreground_app(window_output, "dumpsys window")
        result["device_id"] = device_id
        return result

    def package_validation(self, device_id, package_name):
        device_id = validate_device_id(device_id)
        package_name = validate_package_name(package_name)
        package_output = self._runner().run(["-s", device_id, "shell", "pm", "list", "packages", package_name])
        resolve_output = self._runner().run(
            ["-s", device_id, "shell", "cmd", "package", "resolve-activity", "--brief", package_name]
        )
        return parse_package_validation(device_id, package_name, package_output, resolve_output)

    def _runner(self):
        if self.adb_runner is None:
            self.adb_runner = AdbRunner()
        return self.adb_runner


def resolve_adb_path(which=shutil.which, exists=os.path.exists):
    if exists(BUNDLED_WINDOWS_ADB):
        return BUNDLED_WINDOWS_ADB
    path_adb = which("adb")
    if path_adb:
        return path_adb
    raise TargetDiscoveryError("adb command not found")


def parse_adb_devices(output):
    devices = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2 or parts[1] != "device":
            continue
        device_id = parts[0]
        devices.append(
            {
                "id": device_id,
                "uri": "Android:///%s" % device_id,
                "status": "device",
                "label": device_id,
            }
        )
    return devices


def parse_foreground_app(output, source):
    for pattern in FOREGROUND_PATTERNS:
        match = pattern.search(output)
        if match:
            return {
                "package_name": match.group(1),
                "activity": match.group(2),
                "source": source,
            }
    raise TargetDiscoveryError("foreground app not found")


def parse_package_validation(device_id, package_name, package_output, resolve_output):
    installed = ("package:%s" % package_name) in package_output
    activity = _parse_resolved_activity(package_name, resolve_output)
    warnings = []
    if not installed:
        warnings.append("包名未安装")
    elif not activity:
        warnings.append("包名存在，但未发现可启动 Activity")
    return {
        "device_id": device_id,
        "package_name": package_name,
        "installed": installed,
        "launchable": bool(activity),
        "activity": activity,
        "warnings": warnings,
    }


def validate_device_id(value):
    if not isinstance(value, str) or not DEVICE_ID_RE.match(value):
        raise TargetDiscoveryError("invalid device id")
    return value


def validate_package_name(value):
    if not isinstance(value, str) or not PACKAGE_NAME_RE.match(value):
        raise TargetDiscoveryError("invalid package name")
    return value


def _parse_resolved_activity(package_name, output):
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "No activity found" in line:
            continue
        prefix = package_name + "/"
        if line.startswith(prefix):
            return line[len(prefix) :]
    return ""
```

- [x] **Step 2: Run GREEN**

Run:

```powershell
python -m unittest tests.test_game_reverse_target_discovery
```

Expected: all tests pass.

- [x] **Step 3: Add fake-runner behavior tests**

Append these tests to `TestTargetDiscoveryParsing` before the `if __name__ == "__main__":` block:

```python
    def test_target_discovery_runs_fixed_adb_commands(self):
        from game_reverse.target_discovery import TargetDiscovery

        class FakeRunner:
            def __init__(self):
                self.calls = []

            def run(self, args):
                self.calls.append(args)
                if args == ["devices"]:
                    return "List of devices attached\nemulator-5554\tdevice\n"
                if args[-2:] == ["activity", "activities"]:
                    return (
                        "topResumedActivity=ActivityRecord{67a175a u0 "
                        "com.redlinegames.matchsniper3d/com.unity3d.player.UnityPlayerActivity t57}\n"
                    )
                if args[-4:] == ["pm", "list", "packages", "com.redlinegames.matchsniper3d"]:
                    return "package:com.redlinegames.matchsniper3d\n"
                if args[-4:] == ["package", "resolve-activity", "--brief", "com.redlinegames.matchsniper3d"]:
                    return "com.redlinegames.matchsniper3d/com.unity3d.player.UnityPlayerActivity\n"
                return ""

        runner = FakeRunner()
        discovery = TargetDiscovery(adb_runner=runner)

        self.assertEqual(discovery.list_devices()[0]["id"], "emulator-5554")
        self.assertEqual(
            discovery.foreground_app("emulator-5554")["package_name"],
            "com.redlinegames.matchsniper3d",
        )
        self.assertTrue(
            discovery.package_validation(
                "emulator-5554",
                "com.redlinegames.matchsniper3d",
            )["launchable"]
        )
        self.assertIn(["devices"], runner.calls)
```

- [x] **Step 4: Run target discovery tests**

Run:

```powershell
python -m unittest tests.test_game_reverse_target_discovery
```

Expected: all tests pass.

- [x] **Step 5: Commit target discovery module**

Run:

```powershell
git add game_reverse/target_discovery.py tests/test_game_reverse_target_discovery.py
git commit -m "Add Android target discovery parser"
```

Expected: commit succeeds.

## Task 3: Web Service Discovery Methods

**Files:**
- Modify: `game_reverse/web_service.py`
- Modify: `tests/test_game_reverse_web_service.py`

- [x] **Step 1: Add failing service tests**

In `tests/test_game_reverse_web_service.py`, add this fake after `FakeRunner`:

```python
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
```

Add these tests to `TestGameReverseWebService`:

```python
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
```

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_game_reverse_web_service
```

Expected: fail because `GameReverseWebService.__init__()` does not accept `target_discovery`.

- [x] **Step 3: Implement service methods**

In `game_reverse/web_service.py`, add import:

```python
from game_reverse.target_discovery import TargetDiscovery, TargetDiscoveryError
```

Change `__init__` signature and body:

```python
    def __init__(self, output_root=None, runner=None, executors=None, target_discovery=None):
        self.output_root = output_root or "game_reverse/outputs/sessions"
        self.runner = runner or run_loop
        self.executors = executors or create_default_registry(self.runner)
        self.target_discovery = target_discovery or TargetDiscovery()
        self.runs = {}
        self.events = {}
        self.lock = threading.Lock()
        self.run_counter = 0
```

Add public methods after `config()`:

```python
    def list_devices(self):
        try:
            return {"devices": self.target_discovery.list_devices()}
        except TargetDiscoveryError as exc:
            raise ValidationError(str(exc))

    def foreground_app(self, device_id):
        try:
            return self.target_discovery.foreground_app(device_id)
        except TargetDiscoveryError as exc:
            raise ValidationError(str(exc))

    def package_validation(self, device_id, package_name):
        try:
            return self.target_discovery.package_validation(device_id, package_name)
        except TargetDiscoveryError as exc:
            raise ValidationError(str(exc))
```

- [x] **Step 4: Run service tests**

Run:

```powershell
python -m unittest tests.test_game_reverse_web_service
```

Expected: all tests pass.

- [x] **Step 5: Commit service integration**

Run:

```powershell
git add game_reverse/web_service.py tests/test_game_reverse_web_service.py
git commit -m "Expose target discovery through web service"
```

Expected: commit succeeds.

## Task 4: HTTP Discovery Routes

**Files:**
- Modify: `game_reverse/web_server.py`
- Modify: `tests/test_game_reverse_web_server.py`

- [x] **Step 1: Add failing HTTP route tests**

Add these methods to `FakeService` in `tests/test_game_reverse_web_server.py`:

```python
    def list_devices(self):
        return {"devices": [{"id": "emulator-5554", "uri": "Android:///emulator-5554"}]}

    def foreground_app(self, device_id):
        return {
            "device_id": device_id,
            "package_name": "com.redlinegames.matchsniper3d",
            "activity": "com.unity3d.player.UnityPlayerActivity",
        }

    def package_validation(self, device_id, package_name):
        return {
            "device_id": device_id,
            "package_name": package_name,
            "installed": True,
            "launchable": True,
            "activity": "com.unity3d.player.UnityPlayerActivity",
            "warnings": [],
        }
```

Add tests to `TestGameReverseWebServer`:

```python
    def test_devices_endpoint_returns_json(self):
        result = self.get_json("/api/devices")

        self.assertEqual(result["devices"][0]["id"], "emulator-5554")

    def test_foreground_endpoint_returns_json(self):
        result = self.get_json("/api/devices/emulator-5554/foreground")

        self.assertEqual(result["device_id"], "emulator-5554")
        self.assertEqual(result["package_name"], "com.redlinegames.matchsniper3d")

    def test_package_validation_endpoint_returns_json(self):
        result = self.get_json(
            "/api/devices/emulator-5554/packages/com.redlinegames.matchsniper3d/validation"
        )

        self.assertTrue(result["launchable"])
        self.assertEqual(result["activity"], "com.unity3d.player.UnityPlayerActivity")
```

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_game_reverse_web_server
```

Expected: the three new tests fail with `HTTP Error 404`.

- [x] **Step 3: Add route handling**

In `game_reverse/web_server.py`, add the new routes before the generic `/api/runs/` route:

```python
                elif path == "/api/devices":
                    self._send_json(service.list_devices())
                elif path.startswith("/api/devices/") and path.endswith("/foreground"):
                    self._handle_get_foreground(path)
                elif path.startswith("/api/devices/") and path.endswith("/validation"):
                    self._handle_get_package_validation(path)
```

Add handler methods after `_handle_get_run_events`:

```python
        def _handle_get_foreground(self, path):
            device_id = unquote(path[len("/api/devices/") : -len("/foreground")])
            if not device_id:
                self._send_error(404, "not found")
                return
            self._send_json(service.foreground_app(device_id))

        def _handle_get_package_validation(self, path):
            prefix = "/api/devices/"
            suffix = "/validation"
            middle = path[len(prefix) : -len(suffix)]
            marker = "/packages/"
            if marker not in middle:
                self._send_error(404, "not found")
                return
            device_id, package_name = middle.split(marker, 1)
            if not device_id or not package_name:
                self._send_error(404, "not found")
                return
            self._send_json(service.package_validation(unquote(device_id), unquote(package_name)))
```

- [x] **Step 4: Run HTTP tests**

Run:

```powershell
python -m unittest tests.test_game_reverse_web_server
```

Expected: all tests pass.

- [x] **Step 5: Commit HTTP routes**

Run:

```powershell
git add game_reverse/web_server.py tests/test_game_reverse_web_server.py
git commit -m "Add target discovery API routes"
```

Expected: commit succeeds.

## Task 5: Web Static Contract Tests

**Files:**
- Modify: `tests/test_web_console_static.py`

- [x] **Step 1: Add failing HTML and JS assertions**

In `test_index_wires_assets_and_sample_data`, add:

```python
        self.assertIn('id="detect-devices-button"', html)
        self.assertIn('id="use-foreground-app-button"', html)
        self.assertIn('id="validate-target-button"', html)
        self.assertIn('id="target-config-status"', html)
        self.assertIn("检测设备", html)
        self.assertIn("使用当前前台应用", html)
        self.assertIn("校验配置", html)
```

In `test_app_declares_static_only_boundary`, add:

```python
        self.assertIn("/api/devices", script)
        self.assertIn("wireTargetConfigControls", script)
        self.assertIn("detectDevices", script)
        self.assertIn("useForegroundApp", script)
        self.assertIn("validateTargetConfig", script)
```

In `test_touched_web_files_use_readable_chinese`, add:

```python
        self.assertIn("检测设备", html)
        self.assertIn("使用当前前台应用", html)
        self.assertIn("校验配置", html)
        self.assertIn("未检测设备", script)
```

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_web_console_static
```

Expected: fail because the HTML buttons and JavaScript functions do not exist yet.

## Task 6: Web HTML Controls

**Files:**
- Modify: `web/index.html`

- [x] **Step 1: Add smart config controls under the edit grid**

Immediately after:

```html
</div>

<div class="mission-card">
```

where the closing `</div>` belongs to `<div class="edit-grid" id="config-grid">`, insert:

```html
        <div class="target-tools" id="target-tools">
          <button class="secondary-button" id="detect-devices-button" type="button">检测设备</button>
          <button class="secondary-button" id="use-foreground-app-button" type="button">使用当前前台应用</button>
          <button class="secondary-button" id="validate-target-button" type="button">校验配置</button>
        </div>
        <div class="target-status" id="target-config-status">未检测设备</div>
```

Do not remove the existing `device-uri-input` or `package-name-input`.

- [x] **Step 2: Run HTML-focused tests**

Run:

```powershell
python -m unittest tests.test_web_console_static
```

Expected: HTML assertions pass; JavaScript function assertions still fail.

- [x] **Step 3: Keep HTML changes uncommitted for the JS task**

Do not commit after this task. The static test contract intentionally remains red until Task 7 adds the JavaScript functions. Keep `web/index.html` and `tests/test_web_console_static.py` in the working tree for Task 7.

Expected: `git status --short` shows modified `web/index.html` and `tests/test_web_console_static.py`.

## Task 7: Web JavaScript Behavior

**Files:**
- Modify: `web/app.js`

- [x] **Step 1: Wire smart target buttons on DOM ready**

In the `DOMContentLoaded` handler, after `wireUnsafeActionToggle();`, add:

```javascript
  wireTargetConfigControls();
```

- [x] **Step 2: Add target config functions before `wireStartButton()`**

Add:

```javascript
function wireTargetConfigControls() {
  const detectButton = document.getElementById("detect-devices-button");
  const foregroundButton = document.getElementById("use-foreground-app-button");
  const validateButton = document.getElementById("validate-target-button");

  if (detectButton) {
    detectButton.addEventListener("click", detectDevices);
  }
  if (foregroundButton) {
    foregroundButton.addEventListener("click", useForegroundApp);
  }
  if (validateButton) {
    validateButton.addEventListener("click", validateTargetConfig);
  }
}

function detectDevices() {
  setTargetConfigStatus("正在检测设备...", "info");
  return fetch(`${API_BASE}/api/devices`)
    .then((response) => readJsonOrThrow(response, "检测设备失败"))
    .then((data) => {
      const devices = data.devices || [];
      if (devices.length === 0) {
        setTargetConfigStatus("未检测到在线设备", "warning");
        return devices;
      }
      if (devices.length === 1) {
        setInputValue("device-uri-input", devices[0].uri || `Android:///${devices[0].id}`);
        setTargetConfigStatus(`已连接 ${devices[0].id}`, "ok");
        return devices;
      }
      setInputValue("device-uri-input", devices[0].uri || `Android:///${devices[0].id}`);
      setTargetConfigStatus(`检测到 ${devices.length} 个设备，已选择 ${devices[0].id}`, "warning");
      return devices;
    })
    .catch((error) => {
      setTargetConfigStatus(error.message, "error");
      return [];
    });
}

function useForegroundApp() {
  const deviceId = readDeviceIdFromInput();
  if (!deviceId) {
    setTargetConfigStatus("设备地址格式不正确", "error");
    return Promise.resolve(null);
  }

  setTargetConfigStatus("正在读取前台应用...", "info");
  return fetch(`${API_BASE}/api/devices/${encodeURIComponent(deviceId)}/foreground`)
    .then((response) => readJsonOrThrow(response, "读取前台应用失败"))
    .then((data) => {
      setInputValue("package-name-input", data.package_name || "");
      setTargetConfigStatus(`当前前台应用 ${data.package_name}/${data.activity || ""}`, "ok");
      return data;
    })
    .catch((error) => {
      setTargetConfigStatus(error.message, "error");
      return null;
    });
}

function validateTargetConfig() {
  const deviceId = readDeviceIdFromInput();
  const packageName = readInputValue("package-name-input", "");
  if (!deviceId) {
    setTargetConfigStatus("设备地址格式不正确", "error");
    return Promise.resolve(null);
  }
  if (!packageName) {
    setTargetConfigStatus("应用包名不能为空", "error");
    return Promise.resolve(null);
  }

  setTargetConfigStatus("正在校验配置...", "info");
  return fetch(
    `${API_BASE}/api/devices/${encodeURIComponent(deviceId)}/packages/${encodeURIComponent(packageName)}/validation`
  )
    .then((response) => readJsonOrThrow(response, "校验配置失败"))
    .then((data) => {
      if (data.installed && data.launchable) {
        setTargetConfigStatus(`包名可启动：${data.package_name}/${data.activity || ""}`, "ok");
      } else {
        setTargetConfigStatus((data.warnings || ["配置需要确认"]).join("；"), "warning");
      }
      return data;
    })
    .catch((error) => {
      setTargetConfigStatus(error.message, "error");
      return null;
    });
}

function readDeviceIdFromInput() {
  const deviceUri = readInputValue("device-uri-input", "");
  const match = deviceUri.match(/^Android:\/\/(?:[^/]+)?\/([^/?#]+)$/);
  return match ? match[1] : "";
}

function setTargetConfigStatus(message, tone) {
  const status = document.getElementById("target-config-status");
  if (!status) {
    return;
  }
  status.textContent = message;
  status.className = "target-status";
  if (tone) {
    status.classList.add(`is-${tone}`);
  }
}
```

- [x] **Step 3: Disable smart buttons when backend is offline**

In `updateBackendStatus()`, after setting `status.title`, add:

```javascript
  updateTargetConfigControls();
```

Add helper near `setTargetConfigStatus`:

```javascript
function updateTargetConfigControls() {
  ["detect-devices-button", "use-foreground-app-button", "validate-target-button"].forEach((id) => {
    const button = document.getElementById(id);
    if (button) {
      button.disabled = !backendOnline;
    }
  });
}
```

- [x] **Step 4: Run JS/static tests**

Run:

```powershell
node --check web\app.js
python -m unittest tests.test_web_console_static
```

Expected: both pass.

- [x] **Step 5: Commit JavaScript behavior**

Run:

```powershell
git add web/app.js web/index.html tests/test_web_console_static.py
git commit -m "Wire smart target config controls"
```

Expected: commit succeeds.

## Task 8: Web Styles

**Files:**
- Modify: `web/styles.css`

- [x] **Step 1: Add compact target tool styles**

Add near `.edit-grid` or existing form styles:

```css
.target-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 14px 10px;
}

.secondary-button {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  min-height: 34px;
  padding: 0 12px;
}

.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.target-status {
  margin: 0 14px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
  min-height: 34px;
  padding: 8px 10px;
  overflow-wrap: anywhere;
}

.target-status.is-ok {
  border-color: #b9d7c2;
  background: #f0f8f2;
  color: #287044;
}

.target-status.is-warning {
  border-color: #f0c36d;
  background: #fff7e8;
  color: #8a5a00;
}

.target-status.is-error {
  border-color: #efb8b8;
  background: #fff1f1;
  color: #9b2c2c;
}
```

- [x] **Step 2: Run style/static checks**

Run:

```powershell
python -m unittest tests.test_web_console_static
node --check web\app.js
git diff --check
```

Expected: tests pass, JS syntax passes, no whitespace errors.

- [x] **Step 3: Commit styles**

Run:

```powershell
git add web/styles.css
git commit -m "Style smart target config controls"
```

Expected: commit succeeds.

## Task 9: Final Verification And Manual Smoke

**Files:**
- Modify: this plan file only for checkbox status.

- [x] **Step 1: Run final automated tests**

Run:

```powershell
python -m unittest tests.test_game_reverse_target_discovery tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static
node --check web\app.js
git diff --check
git status --short
```

Expected:

- Python tests pass.
- `node --check` exits 0.
- `git diff --check` prints no whitespace errors.
- Only this plan file is modified if all code tasks have already committed.

- [x] **Step 2: Smoke against the local backend if port 8768 is running**

Run:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8768/api/devices"
```

Expected when MuMu is online: JSON contains `devices` with `emulator-5554` or another online device.

Then run:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8768/api/devices/emulator-5554/foreground"
```

Expected when the game is foreground: JSON contains `package_name` such as `com.redlinegames.matchsniper3d`.

If no emulator is online, record the exact error and keep the automated tests as the verification source.

Smoke record:
- `http://127.0.0.1:8768` was already occupied by an older server process without the new discovery routes.
- Started this worktree's server on `http://127.0.0.1:8769` for verification.
- `/api/devices` returned online device `emulator-5554`.
- `/api/devices/emulator-5554/foreground` returned `com.redlinegames.matchsniper3d` and `com.unity3d.player.UnityPlayerActivity`.
- `/api/devices/emulator-5554/packages/com.redlinegames.matchsniper3d/validation` returned `installed: true` and `launchable: true`.

- [x] **Step 3: Mark executed checkboxes**

Mark only completed steps as `[x]` in this plan file.

- [x] **Step 4: Commit plan status**

Run:

```powershell
git add docs/superpowers/plans/2026-06-18-smart-target-config.md
git commit -m "Track smart target config implementation"
```

Expected: commit succeeds.

## Self-Review Checklist

- Spec coverage:
  - Device detection: Tasks 1, 2, 3, 4, 7.
  - Foreground app detection: Tasks 1, 2, 3, 4, 7.
  - Package validation: Tasks 1, 2, 3, 4, 7.
  - Read-only safety boundary: Tasks 1, 2, 4, 7.
  - Web controls and Chinese status: Tasks 5, 6, 7, 8.
  - Final smoke against MuMu: Task 9.
- Browser still cannot send arbitrary shell commands.
- Smart config never enables `tap` or `swipe`.
- Manual inputs remain available and are not erased by discovery failures.
