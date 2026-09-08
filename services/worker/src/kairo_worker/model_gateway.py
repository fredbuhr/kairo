from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from temporalio import activity

from .config import settings

MODEL_CHECKPOINT_KIND = "kairo.model-call"
MODEL_CHECKPOINT_VERSION = 1


class ModelCallOutcomeUnknown(RuntimeError):
    """A previous attempt may have reached the paid provider, so replay must fail closed."""


class ModelCallAccountingUnknown(RuntimeError):
    """A provider result is known but canonical usage commit status is ambiguous."""


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


def deterministic_model_call_key(
    *, task_id: str, workflow_execution_id: str | None, call_slot: str
) -> str:
    """Return a stable call key for one logical model invocation slot in a durable workflow."""

    execution = workflow_execution_id or "no-execution"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:model:{task_id}:{execution}:{call_slot}"))


def read_activity_model_checkpoint() -> dict[str, Any] | None:
    """Read the last persisted model-call heartbeat before the activity emits a new heartbeat."""

    if not activity.in_activity():
        return None
    for detail in reversed(tuple(activity.info().heartbeat_details)):
        if isinstance(detail, dict) and detail.get("kind") == MODEL_CHECKPOINT_KIND:
            return dict(detail)
    return None


def _internal_headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _litellm_headers(idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    if idempotency_key:
        # LiteLLM exposes this identifier in spend logs/response headers. KAIRO still treats it as
        # correlation only; provider execution is protected by the Temporal checkpoint below.
        headers["x-litellm-call-id"] = idempotency_key
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


def _usage_snapshot(usage: ModelUsage) -> dict[str, Any]:
    return {
        "provider_model": usage.provider_model,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": str(usage.cost_usd),
        "cost_reported": usage.cost_reported,
        "litellm_call_id": usage.litellm_call_id,
    }


def _usage_from_snapshot(payload: dict[str, Any]) -> ModelUsage:
    try:
        cost = max(Decimal("0"), Decimal(str(payload.get("cost_usd") or "0")))
    except (InvalidOperation, ValueError):
        cost = Decimal("0")
    return ModelUsage(
        provider_model=str(payload.get("provider_model") or "unknown"),
        prompt_tokens=_non_negative_int(payload.get("prompt_tokens")),
        completion_tokens=_non_negative_int(payload.get("completion_tokens")),
        total_tokens=_non_negative_int(payload.get("total_tokens")),
        cost_usd=cost,
        cost_reported=bool(payload.get("cost_reported")),
        litellm_call_id=(str(payload["litellm_call_id"]) if payload.get("litellm_call_id") else None),
    )


def _result_snapshot(result: ChatCompletionResult) -> dict[str, Any]:
    return {"content": result.content, "usage": _usage_snapshot(result.usage)}


def _result_from_snapshot(payload: dict[str, Any]) -> ChatCompletionResult:
    content = str(payload.get("content") or "")
    usage_payload = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    if not content:
        raise ModelCallOutcomeUnknown("Persisted model checkpoint has no completion content")
    return ChatCompletionResult(
        content=content,
        usage=_usage_from_snapshot(usage_payload),
        raw={"replayed_from_temporal_checkpoint": True},
    )


def _heartbeat_model_checkpoint(
    *, stage: str, idempotency_key: str, result: ChatCompletionResult | None = None
) -> None:
    if not activity.in_activity():
        return
    payload: dict[str, Any] = {
        "kind": MODEL_CHECKPOINT_KIND,
        "version": MODEL_CHECKPOINT_VERSION,
        "stage": stage,
        "idempotency_key": idempotency_key,
    }
    if result is not None:
        payload["result"] = _result_snapshot(result)
    activity.heartbeat(payload)


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
    idempotency_key: str,
    provider: str,
    model_alias: str,
    usage: ModelUsage,
) -> None:
    # The stable UUID makes duplicate/reconciliation candidates explicit even before Core gains a
    # unique model-call ledger key in the next hardening slice.
    stable_correlation = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:model-usage:{idempotency_key}")
    )
    try:
        parent_correlation = str(uuid.UUID(str(correlation_id))) if correlation_id else None
    except (TypeError, ValueError, AttributeError):
        parent_correlation = None
    payload = {
        "task_id": task_id,
        "workflow_execution_id": workflow_execution_id,
        "correlation_id": stable_correlation,
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
            "idempotency_key": idempotency_key,
            "parent_correlation_id": parent_correlation,
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
    idempotency_key: str,
    resume_checkpoint: dict[str, Any] | None = None,
    temperature: float = 0.2,
    estimated_cost_usd: Decimal = Decimal("0"),
    timeout_seconds: float = 90.0,
) -> ChatCompletionResult:
    """Invoke one logical LiteLLM call without blindly replaying an ambiguous paid request.

    Temporal heartbeat details survive activity retries. KAIRO checkpoints immediately before the
    provider request, after receiving a valid response, while committing accounting, and after the
    usage handoff. A retry can therefore reuse a known result, while an attempt whose provider or
    accounting outcome is ambiguous fails closed instead of silently issuing another paid call.

    `x-litellm-call-id` is used for stable proxy correlation only. KAIRO does not assume the proxy or
    the upstream provider implements exactly-once execution.
    """

    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required for durable model calls")

    checkpoint = resume_checkpoint or {}
    if checkpoint.get("kind") == MODEL_CHECKPOINT_KIND and checkpoint.get("idempotency_key") == idempotency_key:
        stage = str(checkpoint.get("stage") or "")
        result_payload = checkpoint.get("result") if isinstance(checkpoint.get("result"), dict) else None
        if stage == "accounted" and result_payload:
            return _result_from_snapshot(result_payload)
        if stage == "completed" and result_payload:
            replayed = _result_from_snapshot(result_payload)
            provider = (
                replayed.usage.provider_model.split("/", 1)[0]
                if "/" in replayed.usage.provider_model
                else "litellm"
            )
            _heartbeat_model_checkpoint(
                stage="accounting", idempotency_key=idempotency_key, result=replayed
            )
            await _record_usage(
                task_id=task_id,
                workflow_execution_id=workflow_execution_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                provider=provider,
                model_alias=model_alias,
                usage=replayed.usage,
            )
            _heartbeat_model_checkpoint(
                stage="accounted", idempotency_key=idempotency_key, result=replayed
            )
            return replayed
        if stage == "accounting":
            raise ModelCallAccountingUnknown(
                f"Model call {idempotency_key} completed, but canonical usage commit status is unknown; "
                "refusing replay until reconciliation is available"
            )
        if stage == "started":
            raise ModelCallOutcomeUnknown(
                f"Model call {idempotency_key} may already have reached the provider; refusing blind replay"
            )

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
    _heartbeat_model_checkpoint(stage="started", idempotency_key=idempotency_key)
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{settings.litellm_url.rstrip('/')}/v1/chat/completions",
            headers=_litellm_headers(idempotency_key),
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

    result = ChatCompletionResult(content=content, usage=usage, raw=data)
    _heartbeat_model_checkpoint(stage="completed", idempotency_key=idempotency_key, result=result)

    provider = usage.provider_model.split("/", 1)[0] if "/" in usage.provider_model else "litellm"
    _heartbeat_model_checkpoint(stage="accounting", idempotency_key=idempotency_key, result=result)
    await _record_usage(
        task_id=task_id,
        workflow_execution_id=workflow_execution_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        provider=provider,
        model_alias=model_alias,
        usage=usage,
    )
    _heartbeat_model_checkpoint(stage="accounted", idempotency_key=idempotency_key, result=result)
    return result
