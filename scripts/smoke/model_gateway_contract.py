#!/usr/bin/env python3
"""Deterministic proof of KAIRO's logical model gateway accounting contract."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import httpx

from kairo_worker import model_gateway


async def main() -> None:
    authorized: list[dict[str, Any]] = []
    recorded: list[dict[str, Any]] = []

    async def fake_authorize(**kwargs: Any) -> None:
        authorized.append(dict(kwargs))

    async def fake_record(**kwargs: Any) -> None:
        recorded.append(dict(kwargs))

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            assert url.endswith("/v1/chat/completions"), url
            payload = kwargs["json"]
            assert payload["model"] == "smart", payload
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                headers={
                    "x-litellm-response-cost": "0.012345",
                    "x-litellm-call-id": "call-fixture-123",
                },
                json={
                    "model": "openai/gpt-fixture",
                    "choices": [{"message": {"content": "fixture completion"}}],
                    "usage": {
                        "prompt_tokens": 101,
                        "completion_tokens": 29,
                        "total_tokens": 130,
                    },
                },
            )

    original_authorize = model_gateway._authorize_model_call
    original_record = model_gateway._record_usage
    original_client = model_gateway.httpx.AsyncClient
    try:
        model_gateway._authorize_model_call = fake_authorize
        model_gateway._record_usage = fake_record
        model_gateway.httpx.AsyncClient = FakeClient

        result = await model_gateway.chat_completion(
            task_id="00000000-0000-0000-0000-000000000001",
            workflow_execution_id="00000000-0000-0000-0000-000000000002",
            correlation_id="00000000-0000-0000-0000-000000000003",
            model_alias="smart",
            estimated_cost_usd=Decimal("0.02"),
            messages=[{"role": "user", "content": "fixture"}],
        )
    finally:
        model_gateway._authorize_model_call = original_authorize
        model_gateway._record_usage = original_record
        model_gateway.httpx.AsyncClient = original_client

    assert result.content == "fixture completion", result
    assert result.usage.provider_model == "openai/gpt-fixture", result.usage
    assert result.usage.prompt_tokens == 101, result.usage
    assert result.usage.completion_tokens == 29, result.usage
    assert result.usage.total_tokens == 130, result.usage
    assert result.usage.cost_usd == Decimal("0.012345"), result.usage
    assert result.usage.cost_reported is True, result.usage
    assert result.usage.litellm_call_id == "call-fixture-123", result.usage

    assert len(authorized) == 1, authorized
    assert authorized[0]["model_alias"] == "smart", authorized
    assert authorized[0]["estimated_cost_usd"] == Decimal("0.02"), authorized

    assert len(recorded) == 1, recorded
    assert recorded[0]["model_alias"] == "smart", recorded
    assert recorded[0]["provider"] == "openai", recorded
    assert recorded[0]["usage"].cost_usd == Decimal("0.012345"), recorded

    missing_cost = model_gateway.parse_usage(
        {
            "model": "ollama/qwen-fixture",
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        },
        httpx.Headers({}),
    )
    assert missing_cost.total_tokens == 5, missing_cost
    assert missing_cost.cost_usd == Decimal("0"), missing_cost
    assert missing_cost.cost_reported is False, missing_cost

    print(
        "MODEL GATEWAY CONTRACT PASS: logical alias authorization, provider usage parsing, "
        "LiteLLM cost capture and canonical accounting handoff behave deterministically"
    )


if __name__ == "__main__":
    asyncio.run(main())
