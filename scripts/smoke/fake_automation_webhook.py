#!/usr/bin/env python3
"""Controlled HTTP boundary for KAIRO automation full-stack smoke proofs.

This deliberately small server models the only Activepieces contract KAIRO depends on: a webhook POST.
It records bounded test-only request metadata, can return a deterministic success response, and can also
accept a POST then drop the connection to simulate an ambiguous side-effect outcome.
"""

from __future__ import annotations

import hashlib
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST = "0.0.0.0"
PORT = 8089

_lock = threading.Lock()
_records: list[dict[str, Any]] = []


def _record(handler: BaseHTTPRequestHandler, body: bytes) -> dict[str, Any]:
    record = {
        "path": handler.path,
        "invocation_id": handler.headers.get("X-Kairo-Automation-Invocation"),
        "correlation_id": handler.headers.get("X-Kairo-Correlation-Id"),
        "content_type": handler.headers.get("Content-Type"),
        "body_size_bytes": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
    }
    try:
        payload = json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict):
        record["json"] = payload
    with _lock:
        _records.append(record)
    return record


class Handler(BaseHTTPRequestHandler):
    server_version = "KairoAutomationSmoke/1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return
        if self.path == "/__records":
            with _lock:
                records = list(_records)
            self._json(200, {"records": records})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        body = self.rfile.read(max(0, min(length, 1_048_576)))
        record = _record(self, body)

        if self.path == "/success":
            self._json(
                202,
                {
                    "accepted": True,
                    "invocation_id": record["invocation_id"],
                    "fixture": "success",
                },
            )
            return

        if self.path == "/ambiguous":
            # The request has definitely reached the downstream boundary, but the caller receives
            # no HTTP status. KAIRO must therefore refuse to replay the webhook automatically.
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            return

        self._json(404, {"error": "unknown_fixture_path"})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"KAIRO automation smoke webhook listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
