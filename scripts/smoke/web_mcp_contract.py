import asyncio

import httpx
from mcp import Client

from nevolium_worker import web_mcp
from nevolium_worker.tool_runtime import _result_payload
from nevolium_worker.web_mcp_bootstrap import EXPECTED_TOOL_NAMES, catalog_item


async def main() -> None:
    async def fake_search(**kwargs):
        assert kwargs["query"] == "Nevolium architecture", kwargs
        assert kwargs["mode"] == "general", kwargs
        return [
            {
                "id": "S1",
                "title": "Nevolium architecture",
                "url": "https://example.com/nevolium",
                "domain": "example.com",
                "snippet": "Canonical state and durable workflows.",
                "published_at": "2026-09-10",
                "engines": ["fixture"],
                "market_score": 0,
            }
        ]

    async def fake_fetch(_client, value: str):
        assert value == "https://example.com/nevolium", value
        return httpx.Response(
            200,
            request=httpx.Request("GET", value),
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body><article>Nevolium keeps canonical state and durable workflows.</article></body></html>",
        )

    original_search = web_mcp.news._search_searxng
    original_fetch = web_mcp.news._fetch_public_html
    original_extract = web_mcp.news.extract
    try:
        web_mcp.news._search_searxng = fake_search
        server = web_mcp.build_server()
        async with Client(server) as client:
            listed = await client.list_tools()
            catalog = [catalog_item(tool) for tool in listed.tools]
            assert {item["name"] for item in catalog} == EXPECTED_TOOL_NAMES, catalog
            for item in catalog:
                assert item["annotations"]["readOnlyHint"] is True, item
                assert item["annotations"]["destructiveHint"] is False, item

            search_result = _result_payload(
                await client.call_tool(
                    "search",
                    {
                        "query": "Nevolium architecture",
                        "language": "fr",
                        "time_range": "month",
                        "max_results": 4,
                    },
                )
            )
            assert not search_result.get("isError", search_result.get("is_error", False)), search_result
            structured = search_result.get("structuredContent") or search_result.get("structured_content")
            assert structured["results"][0]["url"] == "https://example.com/nevolium", structured
            assert "Canonical state" in structured["results"][0]["snippet"], structured

            # The real SSRF guard rejects local/private targets before any network request.
            private_result = _result_payload(
                await client.call_tool("fetch", {"url": "http://127.0.0.1:8000/internal"})
            )
            assert private_result.get("isError", private_result.get("is_error", False)) is True, private_result

            web_mcp.news._fetch_public_html = fake_fetch
            web_mcp.news.extract = lambda *_args, **_kwargs: (
                "Nevolium keeps canonical state and durable workflows. " * 200
            )
            fetch_result = _result_payload(
                await client.call_tool(
                    "fetch", {"url": "https://example.com/nevolium", "max_chars": 1200}
                )
            )
            assert not fetch_result.get("isError", fetch_result.get("is_error", False)), fetch_result
            fetched = fetch_result.get("structuredContent") or fetch_result.get("structured_content")
            assert fetched["final_url"] == "https://example.com/nevolium", fetched
            assert "durable workflows" in fetched["excerpt"], fetched
            assert len(fetched["excerpt"]) <= 1200, fetched
            assert fetched["excerpt_char_limit"] == 1200, fetched
            assert fetched["truncated"] is True, fetched
            assert "text" not in fetched, fetched
    finally:
        web_mcp.news._search_searxng = original_search
        web_mcp.news._fetch_public_html = original_fetch
        web_mcp.news.extract = original_extract

    print(
        "PASS: first-party Web MCP exposes only the expected read-only search/fetch tools, "
        "keeps private destinations blocked and persists only bounded evidence excerpts"
    )


if __name__ == "__main__":
    asyncio.run(main())
