#!/usr/bin/env python3
"""Controlled Rotki API boundary for KAIRO Finance connector proofs.

The fixture implements only the read-only Rotki API contract consumed by KAIRO: authenticate,
user state, asynchronous blockchain-balance refresh, task polling and cached balances. Test-only
control endpoints can change the observed portfolio without changing connector identity.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

HOST = "0.0.0.0"
PORT = 8090

_lock = threading.RLock()
_state: dict[str, Any] = {
    "username": "kairo-smoke",
    "password": "correct-horse-battery-staple",
    "generation": 1,
    "refresh_count": 0,
    "next_task_id": 100,
    "tasks": {},
}


def _balances() -> dict[str, Any]:
    with _lock:
        generation = int(_state["generation"])
    amount = "2" if generation == 1 else "3.25"
    value = "5000" if generation == 1 else "8125"
    return {
        "per_account": {
            "eth": {
                "0x1111111111111111111111111111111111111111": {
                    "assets": {
                        "ETH": {
                            "native": {"amount": amount, "value": value},
                        }
                    },
                    "liabilities": {},
                }
            }
        },
        "last_refresh_ts": {"eth": 1770000000 + generation},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "KairoRotkiSmoke/1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        raw = self.rfile.read(max(0, min(length, 1_048_576)))
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            self._json(200, {"status": "ok"})
            return
        if path == "/__state":
            with _lock:
                payload = {
                    "generation": _state["generation"],
                    "refresh_count": _state["refresh_count"],
                    "task_count": len(_state["tasks"]),
                }
            self._json(200, payload)
            return
        if path == "/api/1/users":
            with _lock:
                username = str(_state["username"])
            self._json(200, {"result": {username: "loggedin"}, "message": ""})
            return
        if path == "/api/1/tasks":
            with _lock:
                completed = sorted(int(key) for key in _state["tasks"])
            self._json(200, {"result": {"completed": completed, "pending": []}, "message": ""})
            return
        if path.startswith("/api/1/tasks/"):
            try:
                task_id = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self._json(404, {"result": None, "message": "unknown task"})
                return
            with _lock:
                result = _state["tasks"].get(task_id)
            if result is None:
                self._json(404, {"result": None, "message": "unknown task"})
                return
            self._json(200, {"result": {"outcome": {"result": result, "message": ""}}, "message": ""})
            return
        if path == "/api/1/balances/blockchains":
            query = parse_qs(parsed.query)
            if query.get("only_cache") == ["true"]:
                self._json(200, {"result": _balances(), "message": ""})
                return
        self._json(404, {"result": None, "message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._body()

        if path == "/__generation":
            try:
                generation = int(body.get("generation"))
            except (TypeError, ValueError):
                self._json(422, {"error": "generation must be integer"})
                return
            if generation not in {1, 2}:
                self._json(422, {"error": "unsupported generation"})
                return
            with _lock:
                _state["generation"] = generation
            self._json(200, {"generation": generation})
            return

        if path.startswith("/api/1/users/") and path.endswith("/authenticate"):
            username = path[len("/api/1/users/") : -len("/authenticate")]
            with _lock:
                expected_user = str(_state["username"])
                expected_password = str(_state["password"])
            if username != expected_user or body.get("password") != expected_password:
                self._json(401, {"result": None, "message": "invalid credentials"})
                return
            self._json(200, {"result": True, "message": ""})
            return

        if path == "/api/1/balances/blockchains":
            if body.get("async_query") is not True:
                self._json(400, {"result": None, "message": "async_query required"})
                return
            balances = _balances()
            with _lock:
                task_id = int(_state["next_task_id"])
                _state["next_task_id"] = task_id + 1
                _state["refresh_count"] = int(_state["refresh_count"]) + 1
                _state["tasks"][task_id] = balances
            self._json(200, {"result": {"task_id": task_id}, "message": ""})
            return

        self._json(404, {"result": None, "message": "not found"})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"KAIRO Rotki smoke API listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
