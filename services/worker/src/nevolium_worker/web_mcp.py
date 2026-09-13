from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal

import httpx
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

from . import activities as news

WEB_MCP_PORT = 8090
MAX_FETCH_EXCERPT_CHARS = 5_000
DEFAULT_FETCH_EXCERPT_CHARS = 3_500


def build_server() -> MCPServer:
    server = MCPServer("Nevolium Web Tools")
    read_only_open_web = ToolAnnotations(read_only_hint=True, open_world_hint=True)

    @server.tool(
        name="search",
        title="Search recent public sources",
        description=(
            "Search recent public web/news sources through Nevolium's private SearXNG service. "
            "Returns titles, URLs, snippets and publication metadata without modifying external state."
        ),
        annotations=read_only_open_web,
    )
    async def search(
        query: Annotated[str, Field(min_length=2, max_length=500)],
        language: Annotated[str, Field(min_length=2, max_length=16)] = "fr",
        time_range: Literal["day", "month", "year"] = "month",
        max_results: Annotated[int, Field(ge=1, le=12)] = 8,
    ) -> dict[str, Any]:
        sources = await news._search_searxng(
            query=query,
            language=language,
            time_range=time_range,
            max_sources=max_results,
            mode="general",
        )
        return {
            "query": query,
            "language": language,
            "time_range": time_range,
            "results": news._public_sources(sources),
        }

    @server.tool(
        name="fetch",
        title="Read a public web page excerpt",
        description=(
            "Fetch one public HTTP(S) page through Nevolium's SSRF-safe reader and return a bounded "
            "main-text excerpt suitable for research evidence. Private/local destinations and redirects "
            "are rejected. The tool is read-only."
        ),
        annotations=read_only_open_web,
    )
    async def fetch(
        url: Annotated[str, Field(min_length=8, max_length=2048)],
        max_chars: Annotated[int, Field(ge=500, le=MAX_FETCH_EXCERPT_CHARS)] = DEFAULT_FETCH_EXCERPT_CHARS,
    ) -> dict[str, Any]:
        canonical = news._canonical_url(url)
        if not canonical:
            raise ValueError("A valid public HTTP(S) URL is required")

        headers = {
            "User-Agent": "Nevolium-Research/0.2 (+self-hosted personal research assistant)",
            "Accept": "text/html,application/xhtml+xml",
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(12.0, connect=5.0),
            follow_redirects=False,
            headers=headers,
        ) as client:
            response = await news._fetch_public_html(client, canonical)
        if response is None:
            raise ValueError("URL is not an admissible public destination")
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type:
            raise ValueError("Nevolium Web fetch currently accepts HTML pages only")
        if len(response.content) > 2_500_000:
            raise ValueError("Page exceeds the Nevolium Web fetch size limit")

        extracted = await asyncio.to_thread(
            news.extract,
            response.text,
            url=str(response.url),
            include_comments=False,
            include_tables=False,
        )
        raw_text = news._clean_text(extracted, MAX_FETCH_EXCERPT_CHARS + 1)
        if not raw_text:
            raise ValueError("No readable main text could be extracted from this page")
        excerpt = raw_text[:max_chars]
        return {
            "url": canonical,
            "final_url": news._canonical_url(str(response.url)) or canonical,
            "excerpt": excerpt,
            "truncated": len(raw_text) > len(excerpt),
            "excerpt_char_limit": max_chars,
        }

    return server


def main() -> None:
    # The endpoint is intentionally reachable only on Nevolium's internal Docker network in this slice.
    # Keep DNS-rebinding protection explicit rather than relying on SDK defaults for a 0.0.0.0 bind.
    transport_security = TransportSecuritySettings(
        allowed_hosts=[
            f"nevolium-web-mcp:{WEB_MCP_PORT}",
            "nevolium-web-mcp:*",
            f"127.0.0.1:{WEB_MCP_PORT}",
            "127.0.0.1:*",
            f"localhost:{WEB_MCP_PORT}",
            "localhost:*",
        ],
        allowed_origins=[],
    )
    build_server().run(
        transport="streamable-http",
        host="0.0.0.0",
        port=WEB_MCP_PORT,
        json_response=True,
        stateless_http=True,
        transport_security=transport_security,
    )


if __name__ == "__main__":
    main()
