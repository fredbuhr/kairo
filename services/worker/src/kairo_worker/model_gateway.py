from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from temporalio import activity

from .config import settings

MODEL_CHECKPOINT_KIND = "kairo.model-call"
MODEL_CHECKPOINT_VERSION = 1
MODEL_CHECKPOINT_BUNDLE_KIND = "kairo.model-call-bundle"
MODEL_CHECKPOINT_BUNDLE_VERSION = 1
MAX_MODEL_CHECKPOINT_SLOTS = 32


class ModelCallOutcomeUnknown(RuntimeError):
    """A previous attempt may have reached the paid provider, so replay must fail closed."""


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


def deterministic_trace_id(
    *, task_id: str, workflow_execution_id: str | None, correlation_id: str | None
) -> str:
    """Return a stable W3C-compatible trace id without importing an observability SDK.

    Canonical KAIRO UUID correlations map directly to their 32 lowercase hexadecimal form. If a
    caller has no canonical correlation UUID, a stable 16-byte identifier is derived from the task
    and workflow identity. Langfuse/LiteLLM remain consumers of this correlation, never its owner.
    """

    if correlation_id:
        try:
            return uuid.UUID(str(correlation_id)).hex
        except (TypeError, ValueError, AttributeError):
            pass
    seed = f"kairo:trace:{task_id}:{workflow_execution_id or 'no-execution'}:{correlation_id or 'none'}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def langfuse_metadata(
    *,
    task_id: str,
    workflow_execution_id: str | None,
    correlation_id: str | None,
    model_alias: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Build correlation-only metadata consumed by LiteLLM's Langfuse OTEL callback."""

    trace_id = deterministic_trace_id(
        task_id=task_id,
        workflow_execution_id=workflow_execution_id,
        correlation_id=correlation_id,
    )
    return {
        "generation_name": "kairo.model.invoke",
        "trace_id": trace_id,
        "session_id": workflow_execution_id or task_id,
        "tags": ["kairo", f"model:{model_alias}"],
        "kairoTaskId": task_id,
        "kairoWorkflowExecutionId": workflow_execution_id,
        "kairoModelCallKey": idempotency_key,
        "kairoModelAlias": model_alias,
    }


def _valid_model_checkpoint(detail: Any) -> dict[str, Any] | None:
    if not isinstance(detail, dict) or detail.get("kind") != MODEL_CHECKPOINT_KIND:
        return None
    key = str(detail.get("idempotency_key") or "").strip()
    if not key:
        return None
    normalized = dict(detail)
    normalized["idempotency_key"] = key
    return normalized


class ModelCheckpointLedger:
    """Bounded heartbeat state for several logical model-call slots in one Temporal activity.

    A single Temporal heartbeat replaces the previous heartbeat details. Storing only one model-call
    checkpoint is therefore insufficient once an activity performs planning, synthesis, reflection
    or other sequential model turns. The ledger carries all known slots forward on every heartbeat
    while keeping the existing single-checkpoint format readable for rolling upgrades/retries.
    """

    def __init__(self, checkpoints: dict[str, dict[str, Any]] | None = None) -> None:
        self._checkpoints: dict[str, dict[str, Any]] = {}
        for key, checkpoint in (checkpoints or {}).items():
            normalized = _valid_model_checkpoint(checkpoint)
            if normalized is None or normalized["idempotency_key"] != key:
                continue
            self._checkpoints[key] = normalized
        if len(self._checkpoints) > MAX_MODEL_CHECKPOINT_SLOTS:
            raise ValueError("model checkpoint ledger exceeds the bounded slot limit")

    @classmethod
    def from_heartbeat_details(cls, details: tuple[Any, ...] | list[Any]) -> "ModelCheckpointLedger":
        for detail in reversed(tuple(details)):
            if not isinstance(detail, dict):
                continue
            if detail.get("kind") == MODEL_CHECKPOINT_BUNDLE_KIND:
                raw = detail.get("checkpoints")
                if not isinstance(raw, dict):
                    return cls()
                checkpoints: dict[str, dict[str, Any]] = {}
                for key, value in raw.items():
                    normalized = _valid_model_checkpoint(value)
                    if normalized is None:
                        continue
                    stable_key = str(key)
                    if normalized["idempotency_key"] != stable_key:
                        continue
                    checkpoints[stable_key] = normalized
                return cls(checkpoints)

            legacy = _valid_model_checkpoint(detail)
            if legacy is not None:
                return cls({str(legacy["idempotency_key"]): legacy})
        return cls()

    @classmethod
    def from_activity(cls) -> "ModelCheckpointLedger":
        if not activity.in_activity():
            return cls()
        return cls.from_heartbeat_details(tuple(activity.info().heartbeat_details))

    def checkpoint_for(self, idempotency_key: str) -> dict[str, Any] | None:
        checkpoint = self._checkpoints.get(idempotency_key)
        return dict(checkpoint) if checkpoint is not None else None

    def record(self, checkpoint: dict[str, Any]) -> None:
        normalized = _valid_model_checkpoint(checkpoint)
        if normalized is None:
            raise ValueError("invalid model checkpoint")
        key = str(normalized["idempotency_key"])
        if key not in self._checkpoints and len(self._checkpoints) >= MAX_MODEL_CHECKPOINT_SLOTS:
            raise ValueError("model checkpoint ledger exceeds the bounded slot limit")
        self._checkpoints[key] = normalized

    def snapshot(self) -> dict[str, Any]:
        return {
            "kind": MODEL_CHECKPOINT_BUNDLE_KIND,
            "version": MODEL_CHECKPOINT_BUNDLE_VERSION,
            "checkpoints": {key: dict(value) for key, value in sorted(self._checkpoints.items())},
        }


def read_activity_model_checkpoint() -> dict[str, Any] | None:
    """Read the last persisted single model-call heartbeat.

    Kept for existing one-call activities. Multi-call activities should create one
    `ModelCheckpointLedger.from_activity()` and pass it through every logical model slot.
    """

    if not activity.in_activity():
        return None
    for detail in reversed(tuple(activity.info().heartbeat_details)):
        checkpoint = _valid_model_checkpoint(detail)
        if checkpoint is not None:
            return checkpoint
    return None


def _internal_headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _litellm_headers(idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    if idempotency_key:
        # LiteLLM exposes this identifier in spend logs/response headers. KAIRO treats it only as
        # stable correlation; exactly-once provider execution is not assumed.
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
    if not value.is_finite() or value < 0:
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


def _checkpoint_payload(
    *, stage: str, idempotency_key: str, result: ChatCompletionResult | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": MODEL_CHECKPOINT_KIND,
        "version": MODEL_CHECKPOINT_VERSION,
        "stage": stage,
        "idempotency_key": idempotency_key,
    }
    if result is not None:
        payload["result"] = _result_snapshot(result)
    return payload


def _heartbeat_model_checkpoint(
    *,
    stage: str,
    idempotency_key: str,
    result: ChatCompletionResult | None = None,
    checkpoint_ledger: ModelCheckpointLedger | None = None,
) -> None:
    payload = _checkpoint_payload(
        stage=stage,
        idempotency_key=idempotency_key,
        result=result,
    )
    if checkpoint_ledger is not None:
        checkpoint_ledger.record(payload)
        if activity.in_activity():
            activity.heartbeat(checkpoint_ledger.snapshot())
        return
    if activity.in_activity():
        activity.heartbeat(payload)


async def _authorize_model_call(
    *,
    task_id: str,
    workflow_execution_id: str | None,
    model_alias: str,
    estimated_cost_usd: Decimal,
    idempotency_key: str,
) -> None:
    payload = {
        "task_id": task_id,
        "idempotency_key": idempotency_key,
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
        if reason in {"model_call_already_dispatched", "model_call_already_accounted"}:
            raise ModelCallOutcomeUnknown(f"Core refuses blind model replay: {reason}")
        raise RuntimeError(f"KAIRO policy denied model call: {reason}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/model-reservations/start",
            headers=_internal_headers(),
            json={"task_id": task_id, "idempotency_key": idempotency_key},
        )
        if response.status_code == 409:
            raise ModelCallOutcomeUnknown("Core model dispatch claim was already consumed")
        response.raise_for_status()


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
        "idempotency_key": idempotency_key,
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


async def _resume_accounting(
    *,
    task_id: str,
    workflow_execution_id: str | None,
    correlation_id: str | None,
    model_alias: str,
    idempotency_key: str,
    result_payload: dict[str, Any],
    checkpoint_ledger: ModelCheckpointLedger | None = None,
) -> ChatCompletionResult:
    replayed = _result_from_snapshot(result_payload)
    provider = (
        replayed.usage.provider_model.split("/", 1)[0]
        if "/" in replayed.usage.provider_model
        else "litellm"
    )
    _heartbeat_model_checkpoint(
        stage="accounting",
        idempotency_key=idempotency_key,
        result=replayed,
        checkpoint_ledger=checkpoint_ledger,
    )
    # Core owns a unique idempotency key, so an ambiguous HTTP response can be retried safely: an
    # already-committed row is returned without inserting or charging again.
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
        stage="accounted",
        idempotency_key=idempotency_key,
        result=replayed,
        checkpoint_ledger=checkpoint_ledger,
    )
    return replayed


async def chat_completion(
    *,
    task_id: str,
    workflow_execution_id: str | None,
    correlation_id: str | None,
    model_alias: str,
    messages: list[dict[str, Any]],
    idempotency_key: str,
    resume_checkpoint: dict[str, Any] | None = None,
    checkpoint_ledger: ModelCheckpointLedger | None = None,
    temperature: float = 0.2,
    estimated_cost_usd: Decimal = Decimal("0"),
    timeout_seconds: float = 90.0,
) -> ChatCompletionResult:
    """Invoke one logical LiteLLM call without blindly replaying an ambiguous paid request.

    Temporal heartbeat details survive activity retries. KAIRO checkpoints immediately before the
    provider request and stores the validated response before canonical accounting. A known response
    can safely replay its accounting handoff because Core deduplicates by the stable idempotency key.
    If only the pre-provider checkpoint survived, KAIRO fails closed rather than risk a second paid
    request whose first outcome is unknown.

    One-call activities may keep passing `resume_checkpoint`. Activities with several logical model
    turns should share a `ModelCheckpointLedger` so every slot remains available after a later slot
    overwrites the Temporal heartbeat.

    `x-litellm-call-id` is stable proxy correlation only. KAIRO does not assume LiteLLM or the upstream
    provider implements exactly-once execution. Observability metadata is derived from KAIRO IDs and
    has no role in authorization, canonical spend accounting or replay decisions.
    """

    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required for durable model calls")

    checkpoint = resume_checkpoint or (
        checkpoint_ledger.checkpoint_for(idempotency_key) if checkpoint_ledger is not None else None
    ) or {}
    if checkpoint.get("kind") == MODEL_CHECKPOINT_KIND and checkpoint.get("idempotency_key") == idempotency_key:
        stage = str(checkpoint.get("stage") or "")
        result_payload = checkpoint.get("result") if isinstance(checkpoint.get("result"), dict) else None
        if stage == "accounted" and result_payload:
            return _result_from_snapshot(result_payload)
        if stage in {"completed", "accounting"} and result_payload:
            return await _resume_accounting(
                task_id=task_id,
                workflow_execution_id=workflow_execution_id,
                correlation_id=correlation_id,
                model_alias=model_alias,
                idempotency_key=idempotency_key,
                result_payload=result_payload,
                checkpoint_ledger=checkpoint_ledger,
            )
        if stage == "started":
            raise ModelCallOutcomeUnknown(
                f"Model call {idempotency_key} may already have reached the provider; refusing blind replay"
            )
        if stage in {"completed", "accounting", "accounted"}:
            raise ModelCallOutcomeUnknown(
                f"Model call {idempotency_key} checkpoint is missing its validated result"
            )

    await _authorize_model_call(
        task_id=task_id,
        workflow_execution_id=workflow_execution_id,
        model_alias=model_alias,
        estimated_cost_usd=estimated_cost_usd,
        idempotency_key=idempotency_key,
    )

    request = {
        "model": model_alias,
        "temperature": temperature,
        "messages": messages,
        "max_tokens": settings.kairo_model_max_output_tokens,
        "metadata": langfuse_metadata(
            task_id=task_id,
            workflow_execution_id=workflow_execution_id,
            correlation_id=correlation_id,
            model_alias=model_alias,
            idempotency_key=idempotency_key,
        ),
    }
    _heartbeat_model_checkpoint(
        stage="started",
        idempotency_key=idempotency_key,
        checkpoint_ledger=checkpoint_ledger,
    )
    # Absolute deadline, including slow streaming responses. Core's dispatch lease is
    # 300s and proxy timeout 120s; a timed-out request remains financially uncertain.
    async with asyncio.timeout(min(timeout_seconds, 120.0)), httpx.AsyncClient(timeout=min(timeout_seconds, 120.0)) as client:
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
    _heartbeat_model_checkpoint(
        stage="completed",
        idempotency_key=idempotency_key,
        result=result,
        checkpoint_ledger=checkpoint_ledger,
    )

    provider = usage.provider_model.split("/", 1)[0] if "/" in usage.provider_model else "litellm"
    _heartbeat_model_checkpoint(
        stage="accounting",
        idempotency_key=idempotency_key,
        result=result,
        checkpoint_ledger=checkpoint_ledger,
    )
    await _record_usage(
        task_id=task_id,
        workflow_execution_id=workflow_execution_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        provider=provider,
        model_alias=model_alias,
        usage=usage,
    )
    _heartbeat_model_checkpoint(
        stage="accounted",
        idempotency_key=idempotency_key,
        result=result,
        checkpoint_ledger=checkpoint_ledger,
    )
    return result
