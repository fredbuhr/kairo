#!/usr/bin/env python3
"""Offline contract proof for the PydanticAI semantic routing adapter."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from kairo_worker.semantic_router import SemanticRouteTask, semantic_route_with_pydantic_ai


CATALOG = [
    {
        "key": "news.brief",
        "version": 1,
        "title": "News Intelligence briefing",
        "description": "Create a sourced current-news briefing.",
        "input_schema": {
            "type": "object",
            "required": ["query", "mode", "language", "time_range", "max_sources", "output", "voice"],
            "properties": {
                "query": {"type": "string"},
                "mode": {"enum": ["general", "local", "market_impact"]},
                "location": {"type": ["string", "null"]},
                "language": {"type": "string"},
                "time_range": {"enum": ["day", "week", "month"]},
                "max_sources": {"type": "integer"},
                "output": {"enum": ["text", "audio", "both"]},
                "voice": {"type": "string"},
            },
        },
    }
]


def route_json(*, capability: str = "news.brief", confidence: float = 0.94) -> str:
    return json.dumps(
        {
            "outcome": "route",
            "capability": capability,
            "confidence": confidence,
            "parameters": {
                "query": "Que s'est-il passé à Paris ce matin ?",
                "mode": "local",
                "location": "Paris",
                "language": "fr",
                "time_range": "day",
                "max_sources": 10,
                "output": "text",
                "voice": "ff_siwis",
            },
            "rationale": "The request asks for current local events, which maps to News Intelligence.",
        }
    )


async def main() -> None:
    captured: list[list[dict[str, Any]]] = []

    async def valid_completion(messages: list[dict[str, Any]]) -> str:
        captured.append(messages)
        return route_json()

    task = SemanticRouteTask(
        command_id="1d9f7cd5-c4d6-42aa-9edb-3f1a24d9f3ab",
        text="Que s'est-il passé à Paris ce matin ?",
        locale="fr-FR",
        requested_output="auto",
        routable_capabilities=CATALOG,
    )
    proposal = await semantic_route_with_pydantic_ai(task, valid_completion)
    assert proposal.outcome == "route", proposal
    assert proposal.capability == "news.brief", proposal
    assert proposal.confidence == 0.94, proposal
    assert proposal.parameters["location"] == "Paris", proposal
    assert len(captured) == 1, captured
    provider_messages = captured[0]
    assert any(message["role"] == "system" for message in provider_messages), provider_messages
    joined = "\n".join(str(message["content"]) for message in provider_messages)
    assert "news.brief" in joined, joined
    assert "Que s'est-il passé à Paris ce matin ?" in joined, joined

    calls = 0

    async def invented_completion(_: list[dict[str, Any]]) -> str:
        nonlocal calls
        calls += 1
        return route_json(capability="calendar.delete", confidence=0.99)

    invented = await semantic_route_with_pydantic_ai(task, invented_completion)
    assert calls == 1, calls
    assert invented.outcome == "unsupported", invented
    assert invented.capability is None, invented
    assert invented.confidence == 0, invented

    async def unsupported_completion(_: list[dict[str, Any]]) -> str:
        return json.dumps(
            {
                "outcome": "unsupported",
                "capability": None,
                "confidence": 0.12,
                "parameters": {},
                "rationale": "No registered capability can faithfully perform this request.",
            }
        )

    unsupported = await semantic_route_with_pydantic_ai(task, unsupported_completion)
    assert unsupported.outcome == "unsupported", unsupported
    assert unsupported.capability is None, unsupported

    print(
        "SEMANTIC ROUTER CONTRACT PASS: PydanticAI validates structured proposals, receives only the "
        "KAIRO catalog, rejects invented capability keys and uses one model turn per route attempt."
    )


if __name__ == "__main__":
    asyncio.run(main())
