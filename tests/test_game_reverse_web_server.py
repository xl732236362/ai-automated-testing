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

    def start_run(self, payload):
        self.payloads.append(payload)
        return {"id": "fake-run", "status": "completed", "session_dir": "fake-session"}

    def get_run(self, run_id):
        return {"id": run_id, "status": "completed"}

    def list_sessions(self):
        return [{"id": "fake-run", "session_dir": "fake-session"}]

    def session_report(self, run_id):
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

    def test_unknown_api_returns_404(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base_url + "/api/missing", timeout=5)

        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
