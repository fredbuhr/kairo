#!/usr/bin/env python3
"""Deterministic proof for KAIRO's conversational capability router and registry."""

from kairo_core.assistant import route_command
from kairo_core.capabilities import get_capability
from kairo_core.schemas import AssistantCommandCreate


def route(text: str, output: str = "auto"):
    return route_command(AssistantCommandCreate(text=text, locale="fr-FR", output=output))


def main() -> None:
    news = get_capability("news.brief")
    assert news is not None
    assert news.version == 1
    assert news.runtime == "temporal"
    assert news.authority_level == 1
    assert news.metadata["model_gateway"] == "litellm"

    research = get_capability("research.autonomous")
    assert research is not None
    assert research.version == 2
    assert research.runtime == "temporal"
    assert research.authority_level == 1
    assert research.metadata["tool_risk_ceiling"] == "read"
    research_schema = research.input_model.model_json_schema()
    properties = research_schema["properties"]
    assert set(properties) == {"query", "max_tool_calls"}, research_schema
    for authority_field in (
        "project_id",
        "allowed_tool_keys",
        "model_alias",
        "estimated_model_cost_usd",
    ):
        assert authority_field not in properties, research_schema

    deep = route("Fais une recherche approfondie sur les architectures d'agents durables.")
    assert deep is not None
    assert deep.capability == "research.autonomous", deep
    assert deep.route_reason == "deterministic.research", deep
    assert deep.confidence >= 0.98, deep
    assert deep.parameters == {
        "query": "Fais une recherche approfondie sur les architectures d'agents durables.",
        "max_tool_calls": 5,
    }, deep

    ordinary_research = route("Fais une recherche sur les outils MCP pour les assistants personnels.")
    assert ordinary_research is not None
    assert ordinary_research.capability == "research.autonomous", ordinary_research
    assert ordinary_research.parameters["max_tool_calls"] == 3, ordinary_research

    paris = route("Quelles sont les nouvelles du jour sur la ville de Paris ?")
    assert paris is not None
    assert paris.capability == "news.brief"
    assert paris.parameters["mode"] == "local"
    assert paris.parameters["location"] == "Paris"
    assert paris.parameters["time_range"] == "day"
    assert paris.parameters["output"] == "text"
    assert paris.confidence >= 0.98
    assert paris.route_reason == "deterministic.local-news"

    markets = route("Quelles sont les nouvelles qui risquent d'impacter la bourse aujourd'hui ?")
    assert markets is not None
    assert markets.capability == "news.brief"
    assert markets.parameters["mode"] == "market_impact"
    assert markets.parameters["time_range"] == "day"
    assert markets.parameters["output"] == "text"
    assert markets.confidence >= 0.99

    # News remains the specialist route even if the user phrases it as a research request.
    researched_news = route("Fais une recherche sur les actualités qui peuvent impacter la bourse.")
    assert researched_news is not None
    assert researched_news.capability == "news.brief", researched_news
    assert researched_news.parameters["mode"] == "market_impact", researched_news

    spoken = route("Lis-moi les nouvelles qui risquent d'impacter les marchés aujourd'hui.")
    assert spoken is not None
    assert spoken.parameters["mode"] == "market_impact"
    assert spoken.parameters["output"] == "both"

    weekly = route("Quelles sont les nouvelles locales de la semaine ?")
    assert weekly is not None
    assert weekly.parameters["mode"] == "local"
    assert weekly.parameters["time_range"] == "week"

    monthly = route("Résume les actualités du mois.", output="audio")
    assert monthly is not None
    assert monthly.parameters["mode"] == "general"
    assert monthly.parameters["time_range"] == "month"
    assert monthly.parameters["output"] == "audio"

    market_without_news_word = route("Quels événements risquent d'affecter le CAC 40 aujourd'hui ?")
    assert market_without_news_word is not None
    assert market_without_news_word.parameters["mode"] == "market_impact"

    unsupported = route("Ouvre mon agenda demain matin.")
    assert unsupported is None

    print(
        "ASSISTANT ROUTER PASS: versioned authority-free Research v2, News priority, research routing, "
        "Paris locality, market impact, spoken output, time ranges and unsupported routing are deterministic"
    )


if __name__ == "__main__":
    main()
