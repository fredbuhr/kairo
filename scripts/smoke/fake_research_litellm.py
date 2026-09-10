#!/usr/bin/env python3
"""Deterministic OpenAI-compatible model stand-in for Research crash/replay integration."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_LOCK = threading.Lock()
_CALLS: list[dict[str, str]] = []


def _json(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(format % args, flush=True)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/health", "/health/liveliness"}:
            _json(self, 200, {"status": "ok"})
            return
        if self.path == "/stats":
            with _LOCK:
                calls = list(_CALLS)
            _json(
                self,
                200,
                {
                    "total": len(calls),
                    "planning": sum(1 for call in calls if call["phase"] == "planning"),
                    "synthesis": sum(1 for call in calls if call["phase"] == "synthesis"),
                    "call_ids": [call["call_id"] for call in calls],
                    "calls": calls,
                },
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        rendered = json.dumps(request.get("messages") or [], ensure_ascii=False)

        if "tool_catalog" in rendered and "max_tool_calls" in rendered:
            phase = "planning"
            completion = {
                "calls": [
                    {
                        "tool_key": "web.search",
                        "input": {
                            "query": "KAIRO durable research recovery",
                            "language": "en",
                            "time_range": "month",
                            "max_results": 3,
                        },
                        "rationale": "Use the single approved read-only Web search tool.",
                    }
                ],
                "rationale": "One source-discovery call is sufficient for the recovery proof.",
            }
        elif "allowed_evidence_ids" in rendered and "E1" in rendered:
            phase = "synthesis"
            completion = {
                "answer": "The recovered research run completed from the supplied Web evidence.",
                "claims": [
                    {
                        "text": "The supplied evidence describes durable KAIRO research recovery.",
                        "evidence_ids": ["E1"],
                        "confidence": "high",
                    }
                ],
                "uncertainties": ["This is a deterministic integration fixture."],
            }
        else:
            self.send_error(422, "Expected Research planning or synthesis prompt")
            return

        call_id = self.headers.get("x-litellm-call-id") or "missing-call-id"
        with _LOCK:
            _CALLS.append({"phase": phase, "call_id": call_id})
        print(f"RESEARCH_MODEL_CALL phase={phase} call_id={call_id}", flush=True)

        response = {
            "id": f"chatcmpl-kairo-research-{phase}",
            "object": "chat.completion",
            "created": 1789030000,
            "model": "ollama/research-fixture",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": json.dumps(completion)},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
        }
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("x-litellm-response-cost", "0.001000")
        self.send_header("x-litellm-call-id", call_id)
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("fake Research LiteLLM listening on 0.0.0.0:4000", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 4000), Handler).serve_forever()
