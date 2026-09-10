#!/usr/bin/env python3
"""Small delayed SearXNG-compatible fixture used to interrupt Research mid-tool call."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

_LOCK = threading.Lock()
_REQUESTS = 0


def _json(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except BrokenPipeError:
        pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(format % args, flush=True)

    def do_GET(self) -> None:  # noqa: N802
        global _REQUESTS
        parts = urlsplit(self.path)
        if parts.path == "/stats":
            with _LOCK:
                count = _REQUESTS
            _json(self, 200, {"requests": count})
            return
        if parts.path != "/search":
            self.send_error(404)
            return

        params = parse_qs(parts.query)
        query = (params.get("q") or [""])[0]
        with _LOCK:
            _REQUESTS += 1
            request_number = _REQUESTS
        print(f"RESEARCH_SEARCH_REQUEST number={request_number} query={query!r}", flush=True)

        # Long enough for the integration driver to observe the active call and hard-stop the Worker.
        time.sleep(8 if request_number == 1 else 1)
        _json(
            self,
            200,
            {
                "results": [
                    {
                        "title": "KAIRO durable research recovery fixture",
                        "url": "https://example.com/kairo-recovery",
                        "content": "Durable KAIRO research recovered after a Worker interruption.",
                        "publishedDate": "2026-09-10",
                        "engine": "fixture",
                    }
                ]
            },
        )


if __name__ == "__main__":
    print("fake Research SearXNG listening on 0.0.0.0:8080", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
