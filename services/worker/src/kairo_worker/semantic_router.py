from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent, PromptedOutput, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from temporalio import activity

from .config import settings
from .model_gateway import (
    chat_completion,
    deterministic_model_call_key,
    read_activity_model_checkpoint,
)


class SemanticRouteProposal(BaseModel):
    """A proposal only. Core remains authoritative for capability validity and execution."""

    outcome: Literal["route", "unsupported"]
    capability: str | None = Field(default=None, max_length=120)
    confidence: float = Field(ge=0, le=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=1000)


class SemanticRouteTask(BaseModel):
    command_id: uuid.UUID
    text: str = Field(min_length=2, max_length=4000)
    locale: str = Field(default="fr-FR", min_length=2, max_length=16)
    requested_output: Literal["auto", "text", "audio", "both"] = "auto"
    routable_capabilities: list[dict[str, Any]] = Field(min_length=1)


CompletionFn = Callable[[list[dict[str, Any]]], Awaitable[str]]

SEMANTIC_ROUTER_INSTRUCTIONS = """
You are KAIRO's semantic capability router. You never solve the user's request yourself and you
never call tools. Your only job is to propose exactly one capability from the catalog included in
the user prompt, or return outcome='unsupported'. Never invent a capability key. Preserve the
user's intent in normalized capability parameters. Use a conservative confidence score. If the
catalog does not contain a capability that can faithfully satisfy the request, return unsupported.
""".strip()


def _content_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def render_provider_messages(
    messages: list[ModelMessage], info: AgentInfo
) -> list[dict[str, Any]]:
    """Render the small PydanticAI routing history into provider-neutral chat messages.

    The semantic router intentionally has no function tools. PydanticAI's PromptedOutput schema is
    injected through ``info.instructions``; validation feedback would appear as RetryPromptPart, but
    production routing currently has a zero retry budget to preserve one logical model-call slot.
    """

    rendered: list[dict[str, Any]] = []
    if info.instructions:
        rendered.append({"role": "system", "content": info.instructions})

    for message in messages:
        if isinstance(message, ModelRequest):
            user_parts: list[str] = []
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    rendered.append({"role": "system", "content": _content_to_text(part.content)})
                elif isinstance(part, UserPromptPart):
                    user_parts.append(_content_to_text(part.content))
                elif isinstance(part, RetryPromptPart):
                    user_parts.append(part.model_response())
            if user_parts:
                rendered.append({"role": "user", "content": "\n\n".join(user_parts)})
        elif isinstance(message, ModelResponse):
            text = "\n".join(
                part.content for part in message.parts if isinstance(part, TextPart) and part.content
            )
            if text:
                rendered.append({"role": "assistant", "content": text})

    if not rendered:
        raise RuntimeError("PydanticAI produced no provider messages for semantic routing")
    return rendered


class KairoFunctionModelBridge:
    """PydanticAI model adapter whose only provider access is KAIRO's accounted gateway."""

    def __init__(self, completion: CompletionFn):
        self._completion = completion
        self._calls = 0

    async def __call__(
        self, messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        if self._calls > 0:
            raise RuntimeError(
                "Semantic routing is single-model-turn until KAIRO supports multi-slot replay checkpoints"
            )
        self._calls += 1
        content = await self._completion(render_provider_messages(messages, info))
        return ModelResponse(parts=[TextPart(content)])


async def semantic_route_with_pydantic_ai(
    route_input: SemanticRouteTask,
    completion: CompletionFn,
) -> SemanticRouteProposal:
    catalog = route_input.routable_capabilities
    allowed_keys = {str(item.get("key")) for item in catalog if item.get("key")}
    prompt = {
        "user_command": route_input.text,
        "locale": route_input.locale,
        "requested_output": route_input.requested_output,
        "capability_catalog": catalog,
        "constraints": {
            "allowed_capability_keys": sorted(allowed_keys),
            "must_not_execute": True,
        },
    }
    model = FunctionModel(KairoFunctionModelBridge(completion), model_name="kairo-accounted-gateway")
    agent = Agent(
        model,
        output_type=PromptedOutput(
            SemanticRouteProposal,
            name="KAIRO semantic route proposal",
            description="Choose one registered capability or return unsupported.",
        ),
        instructions=SEMANTIC_ROUTER_INSTRUCTIONS,
        retries=0,
    )
    result = await agent.run(json.dumps(prompt, ensure_ascii=False))
    proposal = result.output
    if proposal.outcome == "route" and proposal.capability not in allowed_keys:
        return SemanticRouteProposal(
            outcome="unsupported",
            confidence=0,
            parameters={},
            rationale="Model proposed a capability outside the KAIRO-provided catalog.",
        )
    return proposal


def _internal_headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


@activity.defn(name="perform_semantic_route")
async def perform_semantic_route(payload: dict[str, Any]) -> dict[str, Any]:
    task_input = SemanticRouteTask.model_validate(payload["task_input"])
    task_id = str(payload["task_id"])
    execution_id = str(payload.get("workflow_execution_id") or "") or None
    correlation_id = str(payload.get("correlation_id") or "") or None
    resume_checkpoint = read_activity_model_checkpoint()
    call_key = deterministic_model_call_key(
        task_id=task_id,
        workflow_execution_id=execution_id,
        call_slot="semantic-route-v1",
    )

    async def accounted_completion(messages: list[dict[str, Any]]) -> str:
        result = await chat_completion(
            task_id=task_id,
            workflow_execution_id=execution_id,
            correlation_id=correlation_id,
            model_alias=settings.kairo_semantic_router_model,
            messages=messages,
            idempotency_key=call_key,
            resume_checkpoint=resume_checkpoint,
            temperature=0.0,
            estimated_cost_usd=Decimal(str(settings.kairo_semantic_router_estimated_cost_usd)),
            timeout_seconds=45.0,
        )
        return result.content

    try:
        proposal = await semantic_route_with_pydantic_ai(task_input, accounted_completion)
    except UnexpectedModelBehavior as exc:
        # One paid/local model call may already have completed. Do not trigger a second hidden model
        # turn just to repair invalid JSON; Core receives a conservative unsupported proposal.
        proposal = SemanticRouteProposal(
            outcome="unsupported",
            confidence=0,
            parameters={},
            rationale=f"PydanticAI rejected the model's structured route output: {str(exc)[:500]}",
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/assistant/commands/{task_input.command_id}/semantic-route",
            headers=_internal_headers(),
            json=proposal.model_dump(mode="json"),
        )
        response.raise_for_status()
        applied = response.json()

    return {
        "kind": "semantic-route",
        "title": f"Semantic route — {task_input.text}"[:320],
        "content": {
            "command_id": str(task_input.command_id),
            "model_alias": settings.kairo_semantic_router_model,
            "proposal": proposal.model_dump(mode="json"),
            "applied": applied,
        },
    }
