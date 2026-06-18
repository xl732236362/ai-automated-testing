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
                if args[-4:] == [
                    "package",
                    "resolve-activity",
                    "--brief",
                    "com.redlinegames.matchsniper3d",
                ]:
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


if __name__ == "__main__":
    unittest.main()
