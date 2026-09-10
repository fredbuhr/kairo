#!/usr/bin/env python3
"""Tiny read-only MCP server used only by autonomous Research integration proofs."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

mcp = MCPServer("KAIRO Research Fixture MCP")
security = TransportSecuritySettings(
    allowed_hosts=["fake-research-mcp:8766"],
    allowed_origins=[],
)


@mcp.tool(
    name="search",
    title="Fixture search",
    description="Return one deterministic read-only evidence record.",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)
def search(
    query: Annotated[str, Field(min_length=2, max_length=500)],
) -> dict[str, Any]:
    return {
        "query": query,
        "result_count": 1,
        "results": [
            {
                "title": "KAIRO Research Fixture",
                "url": "https://example.org/kairo-research-fixture",
                "snippet": "KAIRO keeps research provenance tied to canonical tool invocations.",
            }
        ],
    }


if __name__ == "__main__":
    print("fake Research MCP listening on 0.0.0.0:8766", flush=True)
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8766,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )
