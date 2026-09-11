#!/usr/bin/env python3
"""Deterministic contract proof for KAIRO News Intelligence.

External search/model services are replaced with fixtures so CI validates capability routing,
provenance retention, transient full-text handling, SSRF protection, accounted model metadata and
market fallback without depending on the public internet or paid model credentials.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from kairo_worker import activities, news_activity
from kairo_worker.model_gateway import ChatCompletionResult, ModelUsage


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


async def fake_chat_completion(**kwargs: Any) -> ChatCompletionResult:
    assert kwargs["estimated_cost_usd"] == Decimal("0.01")
    return ChatCompletionResult(
        content=(
            '{"headline":"Paris aujourd\u0027hui — briefing KAIRO",'
            '"summary":"La circulation évolue à Paris [S1]. Les marchés surveillent aussi la BCE [S2].",'
            '"spoken_summary":"La circulation évolue à Paris. Les marchés surveillent aussi la BCE.",'
            '"market_impact":null}'
        ),
        usage=ModelUsage(
            provider_model="openai/gpt-fixture",
            prompt_tokens=120,
            completion_tokens=40,
            total_tokens=160,
            cost_usd=Decimal("0.0042"),
            cost_reported=True,
            litellm_call_id="fixture-call",
        ),
        raw={},
    )


async def unavailable_chat_completion(**_: Any) -> ChatCompletionResult:
    raise RuntimeError("fixture model unavailable")


def no_heartbeat(_: Any) -> None:
    return None


async def main() -> None:
    assert await activities._is_public_http_url("http://127.0.0.1:8000/private") is False
    assert await activities._is_public_http_url("http://localhost:4000/v1") is False
    assert await activities._is_public_http_url("file:///etc/passwd") is False

    news_activity.activity.heartbeat = no_heartbeat
    activities._search_searxng = fake_search
    activities._enrich_sources = fake_enrich
    news_activity.chat_completion = fake_chat_completion

    result = await news_activity.perform_news_brief(
        {
            "task_id": "00000000-0000-0000-0000-000000000001",
            "workflow_execution_id": "00000000-0000-0000-0000-000000000002",
            "correlation_id": "00000000-0000-0000-0000-000000000003",
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
    assert content["model_usage"]["model_alias"] == news_activity.settings.kairo_news_model, content
    assert content["model_usage"]["provider_model"] == "openai/gpt-fixture", content
    assert content["model_usage"]["total_tokens"] == 160, content
    assert content["model_usage"]["cost_usd"] == "0.0042", content
    assert content["model_usage"]["cost_reported"] is True, content

    news_activity.chat_completion = unavailable_chat_completion
    market_result = await news_activity.perform_news_brief(
        {
            "task_id": "00000000-0000-0000-0000-000000000004",
            "workflow_execution_id": "00000000-0000-0000-0000-000000000005",
            "correlation_id": "00000000-0000-0000-0000-000000000006",
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
    assert market["model_usage"] is None, market
    assert "S2" in market["summary"], market

    print(
        "NEWS CONTRACT PASS: sourced briefing, transient article text, accounted model metadata, "
        "SSRF protection and deterministic market fallback behave correctly"
    )


if __name__ == "__main__":
    asyncio.run(main())
