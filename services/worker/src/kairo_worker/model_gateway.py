from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from .config import settings


@dataclass(frozen=True)
class ModelUsage:
    provider_model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    cost_reported: bool
    litellm_call_id: str | None = None


@dataclass(frozen=True)
class ChatCompletionResult:
    content: str
    usage: ModelUsage
    raw: dict[str, Any]


def _internal_headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _litellm_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    return headers


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _response_cost(headers: httpx.Headers) -> tuple[Decimal, bool]:
    """Read LiteLLM's final non-streaming response cost without duplicating provider price tables."""

    raw = headers.get("x-litellm-response-cost")
    if raw is None or not raw.strip():
        return Decimal("0"), False
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return Decimal("0"), False
    if value < 0:
        return Decimal("0"), False
    return value, True


def parse_usage(data: dict[str, Any], headers: httpx.Headers) -> ModelUsage:
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    prompt_tokens = _non_negative_int(usage.get("prompt_tokens"))
    completion_tokens = _non_negative_int(usage.get("completion_tokens"))
    total_tokens = _non_negative_int(usage.get("total_tokens"))
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    cost_usd, cost_reported = _response_cost(headers)
    return ModelUsage(
        provider_model=str(data.get("model") or "unknown"),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        cost_reported=cost_reported,
        litellm_call_id=headers.get("x-litellm-call-id") or headers.get("x-litellm-request-id"),
    )


async def _authorize_model_call(
    *,
    task_id: str,
    workflow_execution_id: str | None,
    model_alias: str,
    estimated_cost_usd: Decimal,
) -> None:
    payload = {
        "task_id": task_id,
        "workflow_execution_id": workflow_execution_id,
        "action": "model.invoke",
        "resource_type": "model_alias",
        "resource_id": model_alias,
        "authority_level": 1,
        "estimated_cost_usd": str(max(Decimal("0"), estimated_cost_usd)),
        "scope": {"model_alias": model_alias},
        "reason": f"KAIRO requests a model call through LiteLLM alias {model_alias}",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/policy/authorize",
            headers=_internal_headers(),
            json=payload,
        )
        response.raise_for_status()
        decision = response.json()
    if not decision.get("allowed"):
        reason = str(decision.get("reason") or "model_call_denied")
        raise RuntimeError(f"KAIRO policy denied model call: {reason}")


async def _record_usage(
    *,
    task_id: str,
    workflow_execution_id: str | None,
    correlation_id: str | None,
    provider: str,
    model_alias: str,
    usage: ModelUsage,
) -> None:
    try:
        correlation = str(uuid.UUID(str(correlation_id))) if correlation_id else str(uuid.uuid4())
    except (TypeError, ValueError, AttributeError):
        correlation = str(uuid.uuid4())
    payload = {
        "task_id": task_id,
        "workflow_execution_id": workflow_execution_id,
        "correlation_id": correlation,
        "provider": provider,
        "model_alias": model_alias,
        "model_name": usage.provider_model,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": str(usage.cost_usd),
        "metadata": {
            "source": "litellm-proxy",
            "cost_reported": usage.cost_reported,
            "litellm_call_id": usage.litellm_call_id,
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/model-usage",
            headers=_internal_headers(),
            json=payload,
        )
        response.raise_for_status()


async def chat_completion(
    *,
    task_id: str,
    workflow_execution_id: str | None,
    correlation_id: str | None,
    model_alias: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.2,
    estimated_cost_usd: Decimal = Decimal("0"),
    timeout_seconds: float = 90.0,
) -> ChatCompletionResult:
    """Invoke a logical LiteLLM alias, then atomically hand usage to KAIRO's canonical ledger.

    The pre-call authorization enforces the task's current remaining budget using the caller's cost
    upper-bound estimate. The post-call ledger uses LiteLLM's non-streaming response-cost header when
    available, while still recording token usage if the proxy cannot price a model (for example a
    private/local model with no configured price).
    """

    await _authorize_model_call(
        task_id=task_id,
        workflow_execution_id=workflow_execution_id,
        model_alias=model_alias,
        estimated_cost_usd=estimated_cost_usd,
    )

    request = {
        "model": model_alias,
        "temperature": temperature,
        "messages": messages,
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{settings.litellm_url.rstrip('/')}/v1/chat/completions",
            headers=_litellm_headers(),
            json=request,
        )
        response.raise_for_status()
        data = response.json()
        usage = parse_usage(data, response.headers)

    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise RuntimeError("LiteLLM returned no completion choice")
    message = choices[0].get("message") or {}
    content = str(message.get("content") or "")
    if not content:
        raise RuntimeError("LiteLLM returned an empty completion")

    provider = usage.provider_model.split("/", 1)[0] if "/" in usage.provider_model else "litellm"
    await _record_usage(
        task_id=task_id,
        workflow_execution_id=workflow_execution_id,
        correlation_id=correlation_id,
        provider=provider,
        model_alias=model_alias,
        usage=usage,
    )
    return ChatCompletionResult(content=content, usage=usage, raw=data)
