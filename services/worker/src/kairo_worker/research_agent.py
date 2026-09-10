from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent, PromptedOutput, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from temporalio import activity
from temporalio.exceptions import ApplicationError

from .config import settings
from .model_gateway import (
    ModelCheckpointLedger,
    chat_completion,
    deterministic_model_call_key,
)
from .semantic_router import render_provider_messages


class PlannedToolCall(BaseModel):
    tool_key: str = Field(min_length=1, max_length=200)
    input: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=1000)


class ResearchPlan(BaseModel):
    calls: list[PlannedToolCall] = Field(default_factory=list, max_length=8)
    rationale: str = Field(min_length=1, max_length=2000)


CompletionFn = Callable[[list[dict[str, Any]]], Awaitable[str]]

RESEARCH_PLANNER_INSTRUCTIONS = """
You are KAIRO's bounded research planner. You do not answer the research question yourself.
Choose only from the explicitly supplied read-only MCP tool catalog. Use the minimum useful number
of calls. Never invent tool keys or fields. Every tool input must follow the provided JSON Schema.
Do not request writes, destructive actions, authentication changes, purchases, messages or other
side effects. If the available tools cannot materially help, return an empty call list and explain
why. The Core independently validates every proposed call and remains authoritative.
""".strip()


class SingleTurnBridge:
    def __init__(self, completion: CompletionFn):
        self._completion = completion
        self._calls = 0

    async def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if self._calls:
            raise RuntimeError("Research planning supports exactly one model turn")
        self._calls += 1
        content = await self._completion(render_provider_messages(messages, info))
        return ModelResponse(parts=[TextPart(content)])


async def plan_research(
    *, query: str, tools: list[dict[str, Any]], max_tool_calls: int, completion: CompletionFn
) -> ResearchPlan:
    allowed = {str(tool.get("key")) for tool in tools if tool.get("key")}
    model = FunctionModel(SingleTurnBridge(completion), model_name="kairo-accounted-gateway")
    agent = Agent(
        model,
        output_type=PromptedOutput(
            ResearchPlan,
            name="KAIRO bounded research plan",
            description="Select zero or more explicitly allowed read-only MCP tools.",
        ),
        instructions=RESEARCH_PLANNER_INSTRUCTIONS,
        retries=0,
    )
    result = await agent.run(
        json.dumps(
            {
                "query": query,
                "max_tool_calls": max_tool_calls,
                "tool_catalog": tools,
                "constraints": {
                    "allowed_tool_keys": sorted(allowed),
                    "read_only": True,
                    "max_tool_calls": max_tool_calls,
                },
            },
            ensure_ascii=False,
        )
    )
    plan = result.output
    if len(plan.calls) > max_tool_calls:
        plan.calls = plan.calls[:max_tool_calls]
    for call in plan.calls:
        if call.tool_key not in allowed:
            raise UnexpectedModelBehavior(f"Planner proposed tool outside allowed catalog: {call.tool_key}")
    return plan


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


async def _get_json(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    response = await client.get(
        f"{settings.kairo_core_url.rstrip('/')}{path}", headers=_headers()
    )
    response.raise_for_status()
    return response.json()


@activity.defn(name="perform_autonomous_research")
async def perform_autonomous_research(payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload["task_id"])
    execution_id = str(payload.get("workflow_execution_id") or "") or None
    correlation_id = str(payload.get("correlation_id") or "") or None
    model_checkpoints = ModelCheckpointLedger.from_activity()

    async with httpx.AsyncClient(timeout=30.0) as client:
        context = await _get_json(client, f"/internal/v1/research/tasks/{task_id}/context")

        tools = context.get("tools") if isinstance(context.get("tools"), list) else []
        query = str(context.get("query") or "")
        max_calls = max(1, min(8, int(context.get("max_tool_calls") or 3)))
        model_alias = str(context.get("model_alias") or "local-fast")
        estimated_cost = Decimal(str(context.get("estimated_model_cost_usd") or "0.01"))
        call_key = deterministic_model_call_key(
            task_id=task_id,
            workflow_execution_id=execution_id,
            call_slot="research-plan-v1",
        )

        async def accounted_completion(messages: list[dict[str, Any]]) -> str:
            result = await chat_completion(
                task_id=task_id,
                workflow_execution_id=execution_id,
                correlation_id=correlation_id,
                model_alias=model_alias,
                messages=messages,
                idempotency_key=call_key,
                checkpoint_ledger=model_checkpoints,
                temperature=0.0,
                estimated_cost_usd=estimated_cost,
                timeout_seconds=45.0,
            )
            return result.content

        if not tools:
            plan = ResearchPlan(calls=[], rationale="No enabled read-only A1 MCP tools are available.")
        else:
            try:
                plan = await plan_research(
                    query=query,
                    tools=tools,
                    max_tool_calls=max_calls,
                    completion=accounted_completion,
                )
            except UnexpectedModelBehavior as exc:
                raise ApplicationError(
                    f"Research planner produced invalid structured output: {str(exc)[:1000]}",
                    non_retryable=True,
                ) from exc

        results: list[dict[str, Any]] = []
        for slot, call in enumerate(plan.calls):
            start = await client.post(
                f"{settings.kairo_core_url.rstrip('/')}/internal/v1/research/tasks/{task_id}/tool-invocations",
                headers=_headers(),
                json={
                    "tool_key": call.tool_key,
                    "input": call.input,
                    "slot": slot,
                    "rationale": call.rationale,
                },
            )
            if start.status_code in {409, 422}:
                raise ApplicationError(
                    f"Core rejected research tool proposal {call.tool_key}: {start.text[:1000]}",
                    non_retryable=True,
                )
            start.raise_for_status()
            started = start.json()
            invocation_id = str(started["invocation_id"])

            deadline = asyncio.get_running_loop().time() + 300.0
            while True:
                child = await _get_json(
                    client, f"/internal/v1/research/tool-invocations/{invocation_id}"
                )
                child_status = str(child.get("status") or "")
                if child_status == "completed":
                    results.append(
                        {
                            "slot": slot,
                            "tool_key": call.tool_key,
                            "input": call.input,
                            "rationale": call.rationale,
                            "invocation_id": invocation_id,
                            "result": child.get("result") or {},
                        }
                    )
                    break
                if child_status == "failed":
                    raise ApplicationError(
                        f"Research tool {call.tool_key} failed: {child.get('error') or 'unknown error'}",
                        non_retryable=True,
                    )
                if asyncio.get_running_loop().time() >= deadline:
                    raise RuntimeError(f"Timed out waiting for research tool {call.tool_key}")
                await asyncio.sleep(1.0)

    return {
        "kind": "autonomous-research",
        "title": f"Research — {query}"[:320],
        "content": {
            "query": query,
            "planner_model_alias": model_alias,
            "plan": plan.model_dump(mode="json"),
            "tool_results": results,
            "tool_call_count": len(results),
            "authority": "read-only-a1-policy-bound-child-tasks",
        },
    }
