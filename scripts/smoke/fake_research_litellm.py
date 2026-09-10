#!/usr/bin/env python3
"""Deterministic OpenAI-compatible model fixture for the Research crash/replay proof."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

COUNTS = {"planning": 0, "synthesis": 0, "unexpected": 0}
LOCK = threading.Lock()


def _metrics() -> dict[str, int]:
    with LOCK:
        return dict(COUNTS)


def _increment(stage: str) -> int:
    with LOCK:
        COUNTS[stage] += 1
        return COUNTS[stage]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib API
        print(format % args, flush=True)

    def _json(self, status: int, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        if self.path in {"/", "/health", "/health/liveliness"}:
            self._json(200, {"status": "ok"})
            return
        if self.path == "/metrics":
            self._json(200, _metrics())
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        rendered = json.dumps(request.get("messages") or [], ensure_ascii=False)

        if "allowed_evidence_ids" in rendered:
            stage = "synthesis"
            content = json.dumps(
                {
                    "answer": "The fixture evidence confirms that KAIRO recovered the research run after the Worker interruption.",
                    "claims": [
                        {
                            "text": "The recovered research run retained the canonical MCP evidence.",
                            "evidence_ids": ["E1"],
                            "confidence": "high",
                        }
                    ],
                    "uncertainties": [],
                }
            )
        elif "tool_catalog" in rendered:
            stage = "planning"
            content = json.dumps(
                {
                    "calls": [
                        {
                            "tool_key": "crash.search",
                            "input": {"query": "KAIRO crash replay fixture"},
                            "rationale": "Collect the single deterministic evidence record.",
                        }
                    ],
                    "rationale": "One explicitly allowed read-only call is sufficient.",
                }
            )
        else:
            stage = "unexpected"
            _increment(stage)
            self._json(422, {"error": "Unknown Research model prompt"})
            return

        call_number = _increment(stage)
        call_id = self.headers.get("x-litellm-call-id") or f"research-{stage}-{call_number}"
        response = {
            "id": f"chatcmpl-kairo-research-{stage}-{call_number}",
            "object": "chat.completion",
            "created": 1789032000,
            "model": "openai/kairo-research-fixture",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
        }
        self._json(
            200,
            response,
            headers={
                "x-litellm-response-cost": "0.001000",
                "x-litellm-call-id": call_id,
            },
        )


if __name__ == "__main__":
    print("fake Research LiteLLM listening on 0.0.0.0:4000", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 4000), Handler).serve_forever()
