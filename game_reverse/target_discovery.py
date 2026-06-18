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
        package_output = self._runner().run(
            ["-s", device_id, "shell", "pm", "list", "packages", package_name]
        )
        resolve_output = self._runner().run(
            [
                "-s",
                device_id,
                "shell",
                "cmd",
                "package",
                "resolve-activity",
                "--brief",
                package_name,
            ]
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
