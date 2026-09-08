#!/usr/bin/env python3
"""Deterministic contract proof for the KAIRO News Intelligence activity.

External search/model services are replaced with fixtures so CI validates capability routing,
provenance retention, transient full-text handling, SSRF protection and market fallback without
depending on the public internet or paid model credentials.
"""

from __future__ import annotations

import asyncio
from typing import Any

from kairo_worker import activities


SOURCES = [
    {
        "id": "S1",
        "title": "Paris adapte son plan de circulation",
        "url": "https://example.test/paris-circulation",
        "domain": "example.test",
        "snippet": "La ville annonce des changements de circulation pour cette semaine.",
        "published_at": "2026-09-08T07:30:00Z",
        "engines": ["fixture"],
        "market_score": 0,
    },
    {
        "id": "S2",
        "title": "La BCE laisse les marchés attentifs aux taux et à l'inflation",
        "url": "https://finance.test/bce-taux",
        "domain": "finance.test",
        "snippet": "Les investisseurs évaluent les taux, l'inflation et les perspectives de croissance.",
        "published_at": "2026-09-08T08:00:00Z",
        "engines": ["fixture"],
        "market_score": 48,
    },
]


async def fake_search(**_: Any) -> list[dict[str, Any]]:
    return [dict(source) for source in SOURCES]


async def fake_enrich(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = [dict(source) for source in sources]
    enriched[0]["analysis_text"] = (
        "Texte principal temporaire extrait de la page. Il ne doit jamais être persisté dans "
        "l'Artifact KAIRO."
    )
    enriched[0]["content_available"] = True
    enriched[1]["content_available"] = False
    return enriched


async def fake_summary(**_: Any) -> dict[str, Any]:
    return {
        "headline": "Paris aujourd'hui — briefing KAIRO",
        "summary": "La circulation évolue à Paris [S1]. Les marchés surveillent aussi la BCE [S2].",
        "spoken_summary": "La circulation évolue à Paris. Les marchés surveillent aussi la BCE.",
        "market_impact": None,
    }


async def unavailable_summary(**_: Any) -> dict[str, Any]:
    raise RuntimeError("fixture model unavailable")


def no_heartbeat(_: Any) -> None:
    return None


async def main() -> None:
    assert await activities._is_public_http_url("http://127.0.0.1:8000/private") is False
    assert await activities._is_public_http_url("http://localhost:4000/v1") is False
    assert await activities._is_public_http_url("file:///etc/passwd") is False

    activities.activity.heartbeat = no_heartbeat
    activities._search_searxng = fake_search
    activities._enrich_sources = fake_enrich
    activities._summarize_with_litellm = fake_summary

    result = await activities.perform_news_brief(
        {
            "task_id": "fixture-local",
            "workflow_id": "fixture-local-workflow",
            "task_title": "Paris news",
            "task_input": {
                "capability": "news.brief",
                "query": "Quelles sont les nouvelles du jour ?",
                "mode": "local",
                "location": "Paris",
                "language": "fr",
                "time_range": "day",
                "max_sources": 10,
            },
        }
    )
    assert result["kind"] == "news-brief", result
    content = result["content"]
    assert "Paris" in content["query"], content
    assert "[S1]" in content["summary"] and "[S2]" in content["summary"], content
    assert len(content["sources"]) == 2, content
    assert content["sources"][0]["content_available"] is True, content
    assert "analysis_text" not in content["sources"][0], content

    activities._summarize_with_litellm = unavailable_summary
    market_result = await activities.perform_news_brief(
        {
            "task_id": "fixture-market",
            "workflow_id": "fixture-market-workflow",
            "task_title": "Market news",
            "task_input": {
                "capability": "news.brief",
                "query": "Quelles nouvelles risquent d'impacter la bourse ?",
                "mode": "market_impact",
                "language": "fr",
                "time_range": "day",
                "max_sources": 10,
            },
        }
    )
    market = market_result["content"]
    assert market["market_impact"]["score"] == 48, market
    assert market["market_impact"]["level"] == "medium", market
    assert market["model_warning"], market
    assert "S2" in market["summary"], market

    print(
        "NEWS CONTRACT PASS: sourced local briefing, transient article text, SSRF protection and "
        "market fallback behave deterministically"
    )


if __name__ == "__main__":
    asyncio.run(main())
