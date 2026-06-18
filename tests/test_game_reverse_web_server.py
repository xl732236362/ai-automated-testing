# -*- coding: utf-8 -*-
"""Tests for the local game_reverse web server."""

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game_reverse.web_server import create_server


class FakeService:
    def __init__(self):
        self.payloads = []

    def health(self):
        return {"status": "ok", "runners": [{"id": "game_reverse", "available": True}]}

    def config(self):
        return {"output_root": "game_reverse/outputs/sessions"}

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

    def start_run(self, payload):
        self.payloads.append(payload)
        return {"id": "fake-run", "status": "completed", "session_dir": "fake-session"}

    def get_run(self, run_id):
        if run_id != "fake-run":
            raise KeyError(run_id)
        return {"id": run_id, "status": "completed"}

    def run_events(self, run_id):
        if run_id != "fake-run":
            raise KeyError(run_id)
        return [{"type": "run_started"}]

    def list_sessions(self):
        return [{"id": "fake-run", "session_dir": "fake-session"}]

    def session_report(self, run_id):
        if run_id != "fake-run":
            raise FileNotFoundError(run_id)
        return {"id": run_id, "final_report": "# Report\n"}


class TestGameReverseWebServer(unittest.TestCase):
    def setUp(self):
        self.service = FakeService()
        self.server = create_server(host="127.0.0.1", port=0, service=self.service)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        self.base_url = "http://127.0.0.1:%s" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get_json(self, path):
        with urlopen(self.base_url + path, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, path, payload):
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_endpoint_returns_json(self):
        result = self.get_json("/api/health")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["runners"][0]["id"], "game_reverse")

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

    def test_post_run_passes_payload_to_service(self):
        payload = {"runner": "game_reverse", "package_name": "com.example.game"}

        result = self.post_json("/api/runs", payload)

        self.assertEqual(result["id"], "fake-run")
        self.assertEqual(self.service.payloads[0]["package_name"], "com.example.game")

    def test_serves_static_web_index(self):
        with urlopen(self.base_url + "/web/index.html", timeout=5) as response:
            html = response.read().decode("utf-8")

        self.assertIn("App/Game", html)
        self.assertIn("app.js", html)

    def test_run_events_endpoint_returns_json(self):
        result = self.get_json("/api/runs/fake-run/events")

        self.assertEqual(result["id"], "fake-run")
        self.assertEqual(result["events"], [{"type": "run_started"}])

    def test_session_report_endpoint_returns_json(self):
        result = self.get_json("/api/sessions/fake-run/report")

        self.assertEqual(result["id"], "fake-run")
        self.assertEqual(result["final_report"], "# Report\n")

    def test_missing_run_returns_json_error(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base_url + "/api/runs/missing-run", timeout=5)

        body = error.exception.read().decode("utf-8")
        result = json.loads(body)
        self.assertEqual(error.exception.code, 404)
        self.assertEqual(result, {"error": "not found"})

    def test_unknown_api_returns_404(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base_url + "/api/missing", timeout=5)

        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
