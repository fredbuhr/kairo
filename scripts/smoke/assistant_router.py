#!/usr/bin/env python3
"""Deterministic proof for KAIRO's high-confidence conversational capability router."""

from kairo_core.assistant import route_command
from kairo_core.schemas import AssistantCommandCreate


def route(text: str, output: str = "auto"):
    return route_command(AssistantCommandCreate(text=text, locale="fr-FR", output=output))


def main() -> None:
    paris = route("Quelles sont les nouvelles du jour sur la ville de Paris ?")
    assert paris is not None
    assert paris.capability == "news.brief"
    assert paris.news_mode == "local"
    assert paris.time_range == "day"
    assert paris.output == "text"
    assert paris.confidence >= 0.98

    markets = route("Quelles sont les nouvelles qui risquent d'impacter la bourse aujourd'hui ?")
    assert markets is not None
    assert markets.capability == "news.brief"
    assert markets.news_mode == "market_impact"
    assert markets.time_range == "day"
    assert markets.output == "text"
    assert markets.confidence >= 0.99

    spoken = route("Lis-moi les nouvelles qui risquent d'impacter les marchés aujourd'hui.")
    assert spoken is not None
    assert spoken.news_mode == "market_impact"
    assert spoken.output == "both"

    weekly = route("Quelles sont les nouvelles locales de la semaine ?")
    assert weekly is not None
    assert weekly.news_mode == "local"
    assert weekly.time_range == "week"

    monthly = route("Résume les actualités du mois.", output="audio")
    assert monthly is not None
    assert monthly.news_mode == "general"
    assert monthly.time_range == "month"
    assert monthly.output == "audio"

    market_without_news_word = route("Quels événements risquent d'affecter le CAC 40 aujourd'hui ?")
    assert market_without_news_word is not None
    assert market_without_news_word.news_mode == "market_impact"

    unsupported = route("Ouvre mon agenda demain matin.")
    assert unsupported is None

    print(
        "ASSISTANT ROUTER PASS: Paris, market impact, spoken briefing, time range and conservative "
        "unsupported-command routing behave deterministically"
    )


if __name__ == "__main__":
    main()
