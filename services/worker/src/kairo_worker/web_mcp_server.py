from __future__ import annotations

import html
import re
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from .config import settings

MAX_SEARCH_RESULTS = 10

mcp = MCPServer(
    "KAIRO Web Research",
    instructions=(
        "Read-only public-web discovery for KAIRO. Tool annotations are hints only; "
        "KAIRO Core remains the authority and policy boundary."
    ),
)


def _clean_text(value: Any, limit: int = 1200) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _canonical_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return ""
        return urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
        )
    except (TypeError, ValueError):
        return ""


def _domain(value: str) -> str:
    try:
        return urlsplit(value).netloc.removeprefix("www.")
    except (TypeError, ValueError):
        return ""


async def _search_searxng(
    *,
    query: str,
    limit: int,
    language: str,
    category: Literal["general", "news"],
    time_range: Literal["", "day", "month", "year"],
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "q": query,
        "categories": category,
        "language": language,
        "format": "json",
        "safesearch": 1,
    }
    if time_range:
        params["time_range"] = time_range

    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        response = await client.get(f"{settings.searxng_url.rstrip('/')}/search", params=params)
        response.raise_for_status()
        payload = response.json()

    raw_results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(raw_results, list):
        return []

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        url = _canonical_url(str(raw.get("url") or ""))
        title = _clean_text(raw.get("title"), 320)
        if not url or not title:
            continue
        title_key = re.sub(r"\W+", " ", title.casefold()).strip()
        if url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title_key)
        engines = raw.get("engines") or ([raw.get("engine")] if raw.get("engine") else [])
        results.append(
            {
                "title": title,
                "url": url,
                "domain": _domain(url),
                "snippet": _clean_text(raw.get("content"), 1200),
                "published_at": raw.get("publishedDate") or raw.get("published_date"),
                "engines": [str(item) for item in engines if item],
            }
        )
        if len(results) >= limit:
            break
    return results


@mcp.tool(
    name="search",
    title="Search the public web",
    description=(
        "Search public web or news results through KAIRO's private SearXNG service. "
        "This tool only discovers sources and does not fetch page bodies or perform side effects."
    ),
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)
async def search(
    query: Annotated[str, Field(min_length=2, max_length=500, description="Search query")],
    limit: Annotated[int, Field(ge=1, le=MAX_SEARCH_RESULTS, description="Maximum results")] = 5,
    language: Annotated[
        str, Field(min_length=2, max_length=32, description="SearXNG language code or auto")
    ] = "auto",
    category: Literal["general", "news"] = "general",
    time_range: Literal["", "day", "month", "year"] = "",
) -> dict[str, Any]:
    """Discover bounded public-web results without modifying external state."""

    cleaned_query = _clean_text(query, 500)
    if len(cleaned_query) < 2:
        raise ValueError("query is empty after normalization")
    results = await _search_searxng(
        query=cleaned_query,
        limit=min(MAX_SEARCH_RESULTS, max(1, limit)),
        language=language,
        category=category,
        time_range=time_range,
    )
    return {
        "query": cleaned_query,
        "category": category,
        "language": language,
        "time_range": time_range or None,
        "result_count": len(results),
        "results": results,
    }


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8765,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
