#!/usr/bin/env python3
"""Deterministic Streamable HTTP MCP server for autonomous Research integration tests."""

from __future__ import annotations

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = MCPServer("KAIRO research fixture")


@mcp.tool()
def company_facts(company: str) -> dict[str, object]:
    """Return deterministic, read-only company facts for a fictional company."""

    return {
        "company": company,
        "revenue_eur_m": 42,
        "employees": 120,
        "founded": 2024,
        "source": "kairo-deterministic-research-fixture",
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    print("fake research MCP listening on 127.0.0.1:8765", flush=True)
    mcp.run(
        "streamable-http",
        host="127.0.0.1",
        port=8765,
        json_response=True,
    )
