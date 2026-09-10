#!/usr/bin/env python3
"""Controllable read-only MCP fixture for the real Worker crash/replay integration proof."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

CALLS = 0
COMPLETIONS = 0
LOCK = threading.Lock()
RELEASE = threading.Event()


def _metrics() -> dict[str, Any]:
    with LOCK:
        return {
            "calls": CALLS,
            "completions": COMPLETIONS,
            "released": RELEASE.is_set(),
        }


class MetricsHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib API
        print(format % args, flush=True)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        if self.path in {"/", "/health"}:
            self._json(200, {"status": "ok", **_metrics()})
            return
        if self.path == "/metrics":
            self._json(200, _metrics())
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        if self.path == "/release":
            RELEASE.set()
            self._json(200, {"released": True, **_metrics()})
            return
        self.send_error(404)


def build_server() -> MCPServer:
    server = MCPServer(
        "KAIRO Research Crash Fixture",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["fake-research-mcp:8765", "localhost:8765", "127.0.0.1:8765"],
        ),
    )

    @server.tool(
        name="search",
        title="Deterministic crash-replay search",
        description="Return one deterministic read-only evidence record after the test releases the call.",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    )
    async def search(
        query: Annotated[str, Field(min_length=2, max_length=500)],
    ) -> dict[str, Any]:
        global CALLS, COMPLETIONS
        with LOCK:
            CALLS += 1
            call_number = CALLS
        print(f"FAKE_RESEARCH_MCP_CALL {call_number} {query}", flush=True)

        released = await asyncio.to_thread(RELEASE.wait, 30.0)
        if not released:
            raise RuntimeError("Crash-replay fixture was not released within 30 seconds")

        with LOCK:
            COMPLETIONS += 1
            completion_number = COMPLETIONS
        print(f"FAKE_RESEARCH_MCP_COMPLETE {completion_number}", flush=True)
        return {
            "query": query,
            "items": [
                {
                    "title": "KAIRO crash/replay fixture",
                    "url": "https://example.invalid/kairo-crash-replay",
                    "snippet": "Canonical MCP evidence survived the Worker interruption without duplicate remote execution.",
                }
            ],
            "fixture_call_number": call_number,
        }

    return server


def _serve_metrics() -> None:
    print("fake Research MCP metrics listening on 0.0.0.0:8766", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8766), MetricsHandler).serve_forever()


def main() -> None:
    threading.Thread(target=_serve_metrics, daemon=True, name="research-mcp-metrics").start()
    build_server().run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8765,
        json_response=True,
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
