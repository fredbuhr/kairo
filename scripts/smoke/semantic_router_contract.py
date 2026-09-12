#!/usr/bin/env python3
"""Offline contract proof for the PydanticAI semantic routing adapter."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from datetime import timedelta
from unittest.mock import patch

import httpx

from nevolium_worker import model_gateway, semantic_router, workflows
from nevolium_worker.semantic_router import SemanticRouteTask, semantic_route_with_pydantic_ai


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


def activity_payload() -> dict[str, Any]:
    return {
        "task_id": "00000000-0000-0000-0000-000000000001",
        "workflow_execution_id": "00000000-0000-0000-0000-000000000002",
        "correlation_id": "00000000-0000-0000-0000-000000000003",
        "workflow_id": "fixture-semantic-budget",
        "task_input": {
            "command_id": "00000000-0000-0000-0000-000000000004",
            "text": "Route this safely",
            "locale": "fr-FR",
            "requested_output": "auto",
            "routable_capabilities": CATALOG,
        },
    }


async def prove_scheduled_bounds() -> None:
    scheduled = []
    payload = activity_payload()

    async def execute(function, value, **options):
        if function is workflows.begin_execution:
            return {"task_title": "fixture", "task_input": {
                **payload["task_input"], "capability": "assistant.route.semantic",
            }}
        if function is workflows.check_policy_gate:
            return {"allowed": True}
        if function is workflows.perform_semantic_route:
            scheduled.append(options)
            return {"kind": "semantic-route"}
        assert function is workflows.complete_execution, function
        return {"status": "completed"}

    with patch.object(workflows.workflow, "execute_activity", execute):
        result = await workflows.TaskExecutionWorkflow().run(payload)
    assert result["status"] == "completed"
    assert len(scheduled) == 1, scheduled
    assert scheduled[0]["start_to_close_timeout"] == timedelta(seconds=180)
    assert scheduled[0]["heartbeat_timeout"] == timedelta(seconds=120)
    assert 60 < semantic_router.SEMANTIC_MODEL_TIMEOUT_SECONDS == 110 < 120 < 180


async def prove_gateway_deadline(delay: float, *, expires: bool) -> None:
    """Real gateway deadline with virtual elapsed time, fake transport and no external services.

    This is not an Ollama performance measurement or a Temporal server retry-count proof.
    """
    loop = asyncio.get_running_loop()
    clock = [loop.time()]
    resume = [None]
    stages, requests, authorizations, usages, applied = [], [], [], [], []

    async def authorize(**kwargs):
        authorizations.append(kwargs)

    async def record(**kwargs):
        usages.append(kwargs)

    def heartbeat(*, stage, idempotency_key, **kwargs):
        stages.append(stage)
        resume[0] = {"kind": model_gateway.MODEL_CHECKPOINT_KIND,
                     "stage": stage, "idempotency_key": idempotency_key}

    class Client:
        def __init__(self, **kwargs):
            self.timeout = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            if url.endswith("/v1/chat/completions"):
                assert self.timeout == 110.0, self.timeout
                assert kwargs["json"]["max_tokens"] == 256
                requests.append(kwargs)
                clock[0] += delay
                # Let the real asyncio.timeout callback run when the virtual deadline passed.
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                data = {"model": "local-fast", "usage": {
                    "prompt_tokens": 924, "completion_tokens": 101, "total_tokens": 1025,
                }, "choices": [{"message": {"content": json.dumps({
                    "outcome": "unsupported", "confidence": 0,
                    "parameters": {}, "rationale": "No fixture capability fits.",
                })}}]}
            else:
                assert url.endswith("/semantic-route"), url
                applied.append(kwargs)
                data = {"status": "unsupported"}
            return httpx.Response(200, request=httpx.Request("POST", url), json=data)

    with (
        patch.object(loop, "time", lambda: clock[0]),
        patch.object(model_gateway.httpx, "AsyncClient", Client),
        patch.object(model_gateway, "_authorize_model_call", authorize),
        patch.object(model_gateway, "_record_usage", record),
        patch.object(model_gateway, "_heartbeat_model_checkpoint", heartbeat),
        patch.object(semantic_router, "read_activity_model_checkpoint", lambda: resume[0]),
        patch.object(model_gateway.settings, "nevolium_model_max_output_tokens", 256),
    ):
        if expires:
            try:
                await semantic_router.perform_semantic_route(activity_payload())
            except TimeoutError:
                pass
            else:
                raise AssertionError("Provider deadline must remain effective")
            assert stages == ["started"], stages
            assert not usages and not applied
            try:
                await semantic_router.perform_semantic_route(activity_payload())
            except semantic_router.ApplicationError as exc:
                assert exc.non_retryable and exc.type == "ModelCallOutcomeUnknown", exc
            else:
                raise AssertionError("An expired call must not be sent again")
        else:
            result = await semantic_router.perform_semantic_route(activity_payload())
            assert result["content"]["applied"]["status"] == "unsupported"
            assert stages == ["started", "completed", "accounting", "accounted"], stages
            assert len(usages) == len(applied) == 1
            assert usages[0]["usage"].total_tokens == 1025
            assert usages[0]["usage"].cost_reported is True
            assert usages[0]["usage"].cost_usd == 0
        assert len(requests) == len(authorizations) == 1


async def main() -> None:
    await prove_scheduled_bounds()
    await prove_gateway_deadline(70, expires=False)
    await prove_gateway_deadline(111, expires=True)

    original_route = semantic_router.semantic_route_with_pydantic_ai

    async def unknown_route(*_: Any) -> semantic_router.SemanticRouteProposal:
        raise semantic_router.ModelCallOutcomeUnknown("fixture outcome unknown")

    semantic_router.semantic_route_with_pydantic_ai = unknown_route
    try:
        try:
            await semantic_router.perform_semantic_route(
                {
                    "task_id": "00000000-0000-0000-0000-000000000001",
                    "workflow_execution_id": "00000000-0000-0000-0000-000000000002",
                    "correlation_id": "00000000-0000-0000-0000-000000000003",
                    "task_input": {
                        "command_id": "00000000-0000-0000-0000-000000000004",
                        "text": "Route this safely",
                        "locale": "fr-FR",
                        "requested_output": "auto",
                        "routable_capabilities": CATALOG,
                    },
                }
            )
        except semantic_router.ApplicationError as exc:
            assert exc.non_retryable is True, exc
            assert exc.type == "ModelCallOutcomeUnknown", exc
        else:
            raise AssertionError("Unknown provider outcomes must stop Temporal retries")
    finally:
        semantic_router.semantic_route_with_pydantic_ai = original_route

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
        "Nevolium catalog, rejects invented capability keys, uses one model turn per route attempt, "
        "accounts a virtual 70-second response within the D04 budget, rejects a virtual "
        "111-second timeout without a second provider call, and makes unknown outcomes non-retryable. "
        "Real cold-start qualification remains a separate target proof."
    )


if __name__ == "__main__":
    asyncio.run(main())
