#!/usr/bin/env python3
"""OpenAI-compatible two-slot model fixture for Research plan + synthesis integration tests."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

_lock = threading.Lock()
_call_ids: list[str] = []


def _json_content(messages: list[dict[str, Any]]) -> dict[str, Any]:
    for message in reversed(messages):
        if str(message.get("role") or "") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib API
        print(format % args, flush=True)

    def _write_json(self, status: int, payload: dict[str, Any], *, call_id: str | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if call_id:
            self.send_header("x-litellm-response-cost", "0.001000")
            self.send_header("x-litellm-call-id", call_id)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        if self.path in {"/", "/health", "/health/liveliness"}:
            self._write_json(200, {"status": "ok"})
            return
        if self.path == "/stats":
            with _lock:
                call_ids = list(_call_ids)
            self._write_json(200, {"call_count": len(call_ids), "call_ids": call_ids})
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        messages = request.get("messages") if isinstance(request.get("messages"), list) else []
        prompt = _json_content(messages)
        call_id = self.headers.get("x-litellm-call-id") or "missing-call-id"

        if "tool_catalog" in prompt:
            proposal: dict[str, Any] = {
                "calls": [
                    {
                        "tool_key": "fixture.company_facts",
                        "input": {"company": "Acme Fixture"},
                        "rationale": "Retrieve the deterministic company evidence fixture.",
                    }
                ],
                "rationale": "One read-only evidence call is sufficient for the fixture question.",
            }
        elif "evidence" in prompt and "allowed_invocation_ids" in prompt:
            allowed = prompt.get("allowed_invocation_ids")
            invocation_ids = [str(value) for value in allowed] if isinstance(allowed, list) else []
            if len(invocation_ids) != 1 or not invocation_ids[0]:
                self.send_error(422, "Expected exactly one canonical research invocation id")
                return
            proposal = {
                "answer": "Acme Fixture has €42 million in revenue and 120 employees in the deterministic evidence fixture.",
                "findings": [
                    {
                        "claim": "Acme Fixture reports €42 million in revenue and 120 employees.",
                        "evidence_invocation_ids": [invocation_ids[0]],
                    }
                ],
                "caveats": ["The evidence is a deterministic CI fixture, not a real company source."],
            }
        else:
            self.send_error(422, "Expected KAIRO research planning or synthesis prompt")
            return

        with _lock:
            _call_ids.append(call_id)

        response = {
            "id": f"chatcmpl-{len(_call_ids)}",
            "object": "chat.completion",
            "created": 1788897600,
            "model": "ollama/qwen3:8b",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": json.dumps(proposal)},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        self._write_json(200, response, call_id=call_id)


if __name__ == "__main__":
    print("fake research LiteLLM listening on 127.0.0.1:4000", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 4000), Handler).serve_forever()
