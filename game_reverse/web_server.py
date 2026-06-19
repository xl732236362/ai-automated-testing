# -*- coding: utf-8 -*-
"""Local HTTP server for the game explorer web console."""

import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from game_reverse.web_service import GameReverseWebService, ValidationError


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_WEB_ROOT = os.path.join(ROOT_DIR, "web")


def create_handler(service=None, web_root=None):
    service = service or GameReverseWebService()
    web_root = os.path.abspath(web_root or DEFAULT_WEB_ROOT)

    class GameReverseWebHandler(BaseHTTPRequestHandler):
        server_version = "GameReverseWeb/0.1"

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path == "/":
                    self._redirect("/web/index.html")
                elif path == "/api/health":
                    self._send_json(service.health())
                elif path == "/api/config":
                    self._send_json(service.config())
                elif path == "/api/devices":
                    self._send_json(service.list_devices())
                elif path.startswith("/api/devices/") and path.endswith("/foreground"):
                    self._handle_get_foreground(path)
                elif path.startswith("/api/devices/") and path.endswith("/validation"):
                    self._handle_get_package_validation(path)
                elif path.startswith("/api/runs/") and path.endswith("/events"):
                    self._handle_get_run_events(path)
                elif path.startswith("/api/runs/"):
                    self._handle_get_run(path)
                elif path == "/api/sessions":
                    self._send_json({"sessions": service.list_sessions()})
                elif path.startswith("/api/sessions/") and path.endswith("/report"):
                    session_id = path[len("/api/sessions/") : -len("/report")]
                    self._send_json(service.session_report(unquote(session_id)))
                elif path.startswith("/api/profiles/"):
                    package_name = path[len("/api/profiles/") :]
                    if not package_name:
                        self._send_error(404, "not found")
                        return
                    self._send_json(service.profile_summary(unquote(package_name)))
                elif path.startswith("/web/"):
                    self._send_static(path)
                else:
                    self._send_error(404, "not found")
            except KeyError:
                self._send_error(404, "not found")
            except FileNotFoundError:
                self._send_error(404, "not found")
            except ValidationError as exc:
                self._send_error(400, str(exc))

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path == "/api/runs":
                    self._send_json(service.start_run(self._read_json_body()))
                else:
                    self._send_error(404, "not found")
            except json.JSONDecodeError:
                self._send_error(400, "invalid json")
            except ValidationError as exc:
                self._send_error(400, str(exc))

        def log_message(self, fmt, *args):
            return

        def _handle_get_run(self, path):
            run_id = unquote(path[len("/api/runs/") :])
            if not run_id:
                self._send_error(404, "not found")
                return
            self._send_json(service.get_run(run_id))

        def _handle_get_run_events(self, path):
            run_id = unquote(path[len("/api/runs/") : -len("/events")])
            if not run_id:
                self._send_error(404, "not found")
                return
            self._send_json({"id": run_id, "events": service.run_events(run_id)})

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

        def _send_static(self, path):
            relative = unquote(path[len("/web/") :])
            relative = relative.replace("\\", "/").lstrip("/")
            file_path = os.path.abspath(os.path.join(web_root, relative))
            if not file_path.startswith(web_root + os.sep) and file_path != web_root:
                self._send_error(403, "forbidden")
                return
            if not os.path.isfile(file_path):
                self._send_error(404, "not found")
                return

            content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            with open(file_path, "rb") as static_file:
                body = static_file.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            if not body:
                return {}
            return json.loads(body)

        def _send_json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status, message):
            self._send_json({"error": message}, status=status)

        def _redirect(self, location):
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

    return GameReverseWebHandler


def create_server(host="127.0.0.1", port=8765, service=None, web_root=None):
    handler = create_handler(service=service, web_root=web_root)
    return ThreadingHTTPServer((host, port), handler)


def main():
    parser = argparse.ArgumentParser(description="Run the local game explorer web console.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    print("Game explorer web console: http://%s:%s/web/index.html" % (args.host, args.port))
    server.serve_forever()


if __name__ == "__main__":
    main()
