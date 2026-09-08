#!/usr/bin/env python3
"""Deterministic proof of KAIRO's logical model gateway accounting and replay contract."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import httpx

from kairo_worker import model_gateway

TASK_ID = "00000000-0000-0000-0000-000000000001"
EXECUTION_ID = "00000000-0000-0000-0000-000000000002"
CORRELATION_ID = "00000000-0000-0000-0000-000000000003"
CALL_KEY = model_gateway.deterministic_model_call_key(
    task_id=TASK_ID,
    workflow_execution_id=EXECUTION_ID,
    call_slot="contract.fixture.v1",
)


def checkpoint(stage: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": model_gateway.MODEL_CHECKPOINT_KIND,
        "version": model_gateway.MODEL_CHECKPOINT_VERSION,
        "stage": stage,
        "idempotency_key": CALL_KEY,
    }
    if stage in {"completed", "accounting", "accounted"}:
        payload["result"] = {
            "content": "fixture completion",
            "usage": {
                "provider_model": "openai/gpt-fixture",
                "prompt_tokens": 101,
                "completion_tokens": 29,
                "total_tokens": 130,
                "cost_usd": "0.012345",
                "cost_reported": True,
                "litellm_call_id": CALL_KEY,
            },
        }
    return payload


async def main() -> None:
    authorized: list[dict[str, Any]] = []
    accounting_attempts: list[dict[str, Any]] = []
    provider_posts: list[dict[str, Any]] = []

    async def fake_authorize(**kwargs: Any) -> None:
        authorized.append(dict(kwargs))

    async def fake_record(**kwargs: Any) -> None:
        accounting_attempts.append(dict(kwargs))

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            assert url.endswith("/v1/chat/completions"), url
            provider_posts.append(dict(kwargs))
            payload = kwargs["json"]
            assert payload["model"] == "smart", payload
            headers = kwargs["headers"]
            assert headers["x-litellm-call-id"] == CALL_KEY, headers
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                headers={
                    "x-litellm-response-cost": "0.012345",
                    "x-litellm-call-id": CALL_KEY,
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

        # 1) Normal invocation reaches the provider exactly once and hands off actual usage.
        result = await model_gateway.chat_completion(
            task_id=TASK_ID,
            workflow_execution_id=EXECUTION_ID,
            correlation_id=CORRELATION_ID,
            model_alias="smart",
            idempotency_key=CALL_KEY,
            estimated_cost_usd=Decimal("0.02"),
            messages=[{"role": "user", "content": "fixture"}],
        )
        assert result.content == "fixture completion", result
        assert result.usage.provider_model == "openai/gpt-fixture", result.usage
        assert result.usage.prompt_tokens == 101, result.usage
        assert result.usage.completion_tokens == 29, result.usage
        assert result.usage.total_tokens == 130, result.usage
        assert result.usage.cost_usd == Decimal("0.012345"), result.usage
        assert result.usage.cost_reported is True, result.usage
        assert result.usage.litellm_call_id == CALL_KEY, result.usage
        assert len(provider_posts) == 1, provider_posts
        assert len(authorized) == 1, authorized
        assert len(accounting_attempts) == 1, accounting_attempts
        assert accounting_attempts[0]["idempotency_key"] == CALL_KEY, accounting_attempts

        # 2) An accounted heartbeat replays the known result without provider or ledger traffic.
        replayed = await model_gateway.chat_completion(
            task_id=TASK_ID,
            workflow_execution_id=EXECUTION_ID,
            correlation_id=CORRELATION_ID,
            model_alias="smart",
            idempotency_key=CALL_KEY,
            resume_checkpoint=checkpoint("accounted"),
            estimated_cost_usd=Decimal("0.02"),
            messages=[{"role": "user", "content": "fixture"}],
        )
        assert replayed.content == "fixture completion", replayed
        assert replayed.raw["replayed_from_temporal_checkpoint"] is True, replayed.raw
        assert len(provider_posts) == 1, provider_posts
        assert len(authorized) == 1, authorized
        assert len(accounting_attempts) == 1, accounting_attempts

        # 3) A completed provider result resumes only the idempotent accounting handoff.
        resumed = await model_gateway.chat_completion(
            task_id=TASK_ID,
            workflow_execution_id=EXECUTION_ID,
            correlation_id=CORRELATION_ID,
            model_alias="smart",
            idempotency_key=CALL_KEY,
            resume_checkpoint=checkpoint("completed"),
            estimated_cost_usd=Decimal("0.02"),
            messages=[{"role": "user", "content": "fixture"}],
        )
        assert resumed.content == "fixture completion", resumed
        assert len(provider_posts) == 1, provider_posts
        assert len(accounting_attempts) == 2, accounting_attempts

        # 4) An ambiguous accounting HTTP outcome retries the same canonical idempotency key.
        retried = await model_gateway.chat_completion(
            task_id=TASK_ID,
            workflow_execution_id=EXECUTION_ID,
            correlation_id=CORRELATION_ID,
            model_alias="smart",
            idempotency_key=CALL_KEY,
            resume_checkpoint=checkpoint("accounting"),
            messages=[{"role": "user", "content": "fixture"}],
        )
        assert retried.content == "fixture completion", retried
        assert len(provider_posts) == 1, provider_posts
        assert len(accounting_attempts) == 3, accounting_attempts
        assert {attempt["idempotency_key"] for attempt in accounting_attempts} == {CALL_KEY}

        # 5) If the prior attempt may have reached the provider, replay fails closed.
        try:
            await model_gateway.chat_completion(
                task_id=TASK_ID,
                workflow_execution_id=EXECUTION_ID,
                correlation_id=CORRELATION_ID,
                model_alias="smart",
                idempotency_key=CALL_KEY,
                resume_checkpoint=checkpoint("started"),
                messages=[{"role": "user", "content": "fixture"}],
            )
        except model_gateway.ModelCallOutcomeUnknown:
            pass
        else:
            raise AssertionError("Ambiguous provider outcome must refuse blind replay")
        assert len(provider_posts) == 1, provider_posts
    finally:
        model_gateway._authorize_model_call = original_authorize
        model_gateway._record_usage = original_record
        model_gateway.httpx.AsyncClient = original_client

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
        "MODEL GATEWAY CONTRACT PASS: stable model-call identity, provider replay refusal, replayable "
        "canonical accounting, usage parsing and LiteLLM cost capture behave deterministically"
    )


if __name__ == "__main__":
    asyncio.run(main())
