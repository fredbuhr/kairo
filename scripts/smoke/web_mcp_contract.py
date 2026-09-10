from __future__ import annotations

import asyncio
from typing import Any

from mcp import Client

from kairo_worker import web_mcp_server


async def main() -> None:
    calls: list[dict[str, Any]] = []
    assert web_mcp_server.WEB_MCP_TRANSPORT_SECURITY.allowed_hosts == [
        "kairo-web-mcp:8765"
    ], web_mcp_server.WEB_MCP_TRANSPORT_SECURITY
    assert web_mcp_server.WEB_MCP_TRANSPORT_SECURITY.allowed_origins == []

    async def fake_search(**kwargs: Any) -> list[dict[str, Any]]:
        calls.append(dict(kwargs))
        return [
            {
                "title": "KAIRO architecture",
                "url": "https://example.org/kairo",
                "domain": "example.org",
                "snippet": "Canonical state belongs to KAIRO.",
                "published_at": None,
                "engines": ["fixture"],
            }
        ]

    original_search = web_mcp_server._search_searxng
    web_mcp_server._search_searxng = fake_search
    try:
        async with Client(web_mcp_server.mcp, raise_exceptions=True) as client:
            listed = await client.list_tools()
            assert len(listed.tools) == 1, listed.tools
            tool = listed.tools[0]
            assert tool.name == "search", tool
            assert tool.annotations is not None, tool
            assert tool.annotations.read_only_hint is True, tool.annotations
            assert tool.annotations.open_world_hint is True, tool.annotations
            properties = tool.input_schema.get("properties") or {}
            assert set(properties) == {"query", "limit", "language", "category", "time_range"}, properties
            assert tool.input_schema.get("required") == ["query"], tool.input_schema

            result = await client.call_tool(
                "search",
                {
                    "query": "  KAIRO   architecture  ",
                    "limit": 3,
                    "language": "fr",
                    "category": "general",
                    "time_range": "month",
                },
            )
            assert result.is_error is False, result
            payload = result.structured_content
            assert payload is not None, result
            assert payload["query"] == "KAIRO architecture", payload
            assert payload["result_count"] == 1, payload
            assert payload["results"][0]["url"] == "https://example.org/kairo", payload
            assert calls == [
                {
                    "query": "KAIRO architecture",
                    "limit": 3,
                    "language": "fr",
                    "category": "general",
                    "time_range": "month",
                }
            ], calls

            invalid = await client.call_tool("search", {"query": "x", "limit": 3})
            assert invalid.is_error is True, invalid
            assert len(calls) == 1, calls
    finally:
        web_mcp_server._search_searxng = original_search

    print(
        "PASS: KAIRO Web MCP exposes one bounded open-web read-only search tool with typed inputs, "
        "structured results and an explicit internal Host allowlist"
    )


if __name__ == "__main__":
    asyncio.run(main())
