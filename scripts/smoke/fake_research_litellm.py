#!/usr/bin/env python3
"""Deterministic OpenAI-compatible model stand-in for autonomous Research integration proofs."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CALLS: list[str] = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib API
        print(format % args, flush=True)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        if self.path == "/stats":
            self._json(200, {"calls": len(CALLS), "stages": CALLS})
            return
        if self.path in {"/", "/health", "/health/liveliness"}:
            self._json(200, {"status": "ok"})
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        rendered = json.dumps(request.get("messages") or [], ensure_ascii=False)

        if "tool_catalog" in rendered and "allowed_tool_keys" in rendered:
            stage = "plan"
            completion = {
                "calls": [
                    {
                        "tool_key": "fixture.search",
                        "input": {"query": "KAIRO canonical research provenance"},
                        "rationale": "Collect one deterministic public evidence record.",
                    }
                ],
                "rationale": "One read-only search is enough for the fixture question.",
            }
        elif "allowed_evidence_ids" in rendered and "grounded_only" in rendered:
            stage = "synthesis"
            completion = {
                "answer": "The fixture evidence states that KAIRO keeps research provenance tied to canonical tool invocations.",
                "claims": [
                    {
                        "text": "KAIRO keeps research provenance tied to canonical tool invocations.",
                        "evidence_ids": ["E1"],
                        "confidence": "high",
                    }
                ],
                "uncertainties": ["This deterministic fixture proves the execution contract, not the broader product claim."],
            }
        else:
            self.send_error(422, "Expected KAIRO Research planning or synthesis prompt")
            return

        CALLS.append(stage)
        response = {
            "id": f"chatcmpl-kairo-research-{stage}-{len(CALLS)}",
            "object": "chat.completion",
            "created": 1789020000,
            "model": "fixture/research-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": json.dumps(completion)},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 60, "total_tokens": 180},
        }
        body = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("x-litellm-response-cost", "0.000100")
        self.send_header(
            "x-litellm-call-id",
            self.headers.get("x-litellm-call-id") or f"research-{stage}-{len(CALLS)}",
        )
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("fake Research LiteLLM listening on 0.0.0.0:4000", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 4000), Handler).serve_forever()
