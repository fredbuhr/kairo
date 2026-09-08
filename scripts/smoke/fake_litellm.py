#!/usr/bin/env python3
"""Tiny OpenAI-compatible LiteLLM stand-in used only by deterministic CI integration proofs."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002 - BaseHTTPRequestHandler API
        print(format % args, flush=True)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path in {"/", "/health", "/health/liveliness"}:
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        text = json.dumps(request.get("messages") or [], ensure_ascii=False)
        if "capability_catalog" not in text or "news.brief" not in text:
            self.send_error(422, "Expected KAIRO semantic-routing catalog")
            return

        proposal = {
            "outcome": "route",
            "capability": "news.brief",
            "confidence": 0.93,
            "parameters": {
                "query": "Que s'est-il passé à Paris ce matin ?",
                "mode": "local",
                "location": "Paris",
                "language": "fr",
                "time_range": "day",
                "max_sources": 10,
                "output": "text",
                "voice": "ff_siwis",
            },
            "rationale": "The ambiguous request is asking for current local events in Paris.",
        }
        response = {
            "id": "chatcmpl-kairo-semantic-ci",
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
            "usage": {"prompt_tokens": 180, "completion_tokens": 90, "total_tokens": 270},
        }
        body = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("x-litellm-response-cost", "0.000100")
        self.send_header(
            "x-litellm-call-id",
            self.headers.get("x-litellm-call-id") or "kairo-semantic-ci",
        )
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("fake LiteLLM listening on 0.0.0.0:4000", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 4000), Handler).serve_forever()
