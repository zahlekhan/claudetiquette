"""Local HTTP server. The Claude hook talks only to this process."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from claudetiquette.engine import Engine, build_engine

HOST = "127.0.0.1"
MAX_BODY = 64_000

_ready = threading.Event()
_engine: Engine | None = None
_lock = threading.Lock()
_error: str | None = None


def port() -> int:
    return int(os.environ.get("CLAUDETIQUETTE_PORT", "47321"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/health":
            self._send(404, {"ready": False, "error": "not found"})
            return
        self._send(200, {"ready": _ready.is_set(), "error": _error})

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/clean":
            self._send(404, {"ready": False, "error": "not found"})
            return
        if not _ready.is_set() or _engine is None:
            self._send(200, {"ready": False, "action": "pass", "error": _error})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > MAX_BODY:
            self._send(400, {"ready": True, "error": "body too large"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            text = payload.get("text", "")
            if not isinstance(text, str):
                raise ValueError("text must be a string")
        except (json.JSONDecodeError, ValueError) as exc:
            self._send(400, {"ready": True, "error": str(exc)})
            return
        with _lock:
            result = _engine.clean(text)
        self._send(200, result)

    def log_message(self, fmt: str, *args):
        # Status only. The prompt stays out of the log.
        print("[claudetiquette] %s" % (fmt % args), flush=True)

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(engine_factory=build_engine) -> None:
    global _engine, _error
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((HOST, port()), Handler)
    print(f"[claudetiquette] listening on http://{HOST}:{port()}", flush=True)

    def _load():
        global _engine, _error
        try:
            _engine = engine_factory()
            _ready.set()
            print("[claudetiquette] ready", flush=True)
        except Exception as exc:  # noqa: BLE001
            _error = str(exc)
            print(f"[claudetiquette] failed to load models: {exc}", flush=True)

    threading.Thread(target=_load, name="claudetiquette-load", daemon=True).start()
    httpd.serve_forever()


if __name__ == "__main__":
    serve()
