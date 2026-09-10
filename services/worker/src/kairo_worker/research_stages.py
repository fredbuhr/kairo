from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import httpx
from pydantic_ai import UnexpectedModelBehavior
from temporalio import activity
from temporalio.exceptions import ApplicationError

from .config import settings
from .model_gateway import ModelCheckpointLedger, chat_completion, deterministic_model_call_key
from .research_agent import (
    ResearchPlan,
    build_evidence_index,
    build_research_evidence,
    no_evidence_synthesis,
    plan_research,
    split_research_model_budget,
    synthesize_research,
)
from .research_context_pack import context_pack_model_records


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


async def _get_json(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    response = await client.get(
        f"{settings.kairo_core_url.rstrip('/')}{path}", headers=_headers()
    )
    response.raise_for_status()
    return response.json()


def _heartbeat_tool_progress(
    *, phase: str, planned_tool_calls: int, active_slot: int | None = None, completed_slots: list[int] | None = None
) -> None:
    if not activity.in_activity():
        return
    payload: dict[str, Any] = {
        "kind": "kairo.research-tool-progress",
        "version": 1,
        "phase": phase,
        "planned_tool_calls": max(0, int(planned_tool_calls)),
        "completed_tool_slots": sorted(set(completed_slots or [])),
    }
    if active_slot is not None:
        payload["active_slot"] = max(0, int(active_slot))
    activity.heartbeat(payload)


@activity.defn(name="prepare_research_plan_stage")
async def prepare_research_plan_stage(payload: dict[str, Any]) -> dict[str, Any]:
    """Produce one bounded research plan as a durable Temporal activity result.

    The activity may use heartbeat checkpoints to avoid blind paid-call replay while it is running,
    but once it completes the validated plan itself is stored in Temporal workflow history. Later
    Worker crashes therefore cannot make the tool-orchestration stage call the planner again.
    """

    task_id = str(payload["task_id"])
    execution_id = str(payload.get("workflow_execution_id") or "") or None
    correlation_id = str(payload.get("correlation_id") or "") or None
    raw_context_pack = payload.get("research_context_pack")
    context_pack = raw_context_pack if isinstance(raw_context_pack, dict) else {"items": []}
    context_evidence = context_pack_model_records(context_pack)
    model_checkpoints = ModelCheckpointLedger.from_activity()

    async with httpx.AsyncClient(timeout=30.0) as client:
        context = await _get_json(client, f"/internal/v1/research/tasks/{task_id}/context")

    tools = context.get("tools") if isinstance(context.get("tools"), list) else []
    query = str(context.get("query") or "")
    max_calls = max(1, min(8, int(context.get("max_tool_calls") or 3)))
    model_alias = str(context.get("model_alias") or "local-fast")
    model_budget = Decimal(str(context.get("estimated_model_cost_usd") or "0.01"))
    planner_uses_model = bool(tools)
    planner_estimated_cost, synthesis_estimated_cost = split_research_model_budget(model_budget)
    if not planner_uses_model:
        planner_estimated_cost = Decimal("0")
        synthesis_estimated_cost = model_budget

    if not tools:
        plan = ResearchPlan(
            calls=[],
            rationale=(
                "No enabled read-only A1 MCP tools are available; synthesis may still use the "
                "Temporal Context Pack snapshot."
            ),
        )
    else:
        planner_call_key = deterministic_model_call_key(
            task_id=task_id,
            workflow_execution_id=execution_id,
            call_slot="research-plan-v1",
        )

        async def accounted_planning_completion(messages: list[dict[str, Any]]) -> str:
            result = await chat_completion(
                task_id=task_id,
                workflow_execution_id=execution_id,
                correlation_id=correlation_id,
                model_alias=model_alias,
                messages=messages,
                idempotency_key=planner_call_key,
                checkpoint_ledger=model_checkpoints,
                temperature=0.0,
                estimated_cost_usd=planner_estimated_cost,
                timeout_seconds=45.0,
            )
            return result.content

        try:
            plan = await plan_research(
                query=query,
                tools=tools,
                max_tool_calls=max_calls,
                completion=accounted_planning_completion,
                context_pack=context_evidence,
            )
        except UnexpectedModelBehavior as exc:
            raise ApplicationError(
                f"Research planner produced invalid structured output: {str(exc)[:1000]}",
                non_retryable=True,
            ) from exc

    return {
        "query": query,
        "model_alias": model_alias,
        "model_budget_usd": str(model_budget),
        "planner_uses_model": planner_uses_model,
        "synthesis_estimated_cost_usd": str(synthesis_estimated_cost),
        "plan": plan.model_dump(mode="json"),
    }


@activity.defn(name="execute_research_tool_stage")
async def execute_research_tool_stage(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute only the already-durable plan and return bounded evidence.

    Core remains authoritative for child ToolInvocation idempotency. Retrying this activity after a
    Worker crash may re-submit a logical slot, but it resolves to the same canonical invocation and
    must not re-run the planner model stage.
    """

    task_id = str(payload["task_id"])
    raw_plan_stage = payload.get("research_plan_stage")
    if not isinstance(raw_plan_stage, dict):
        raise ApplicationError("Research plan stage is missing", non_retryable=True)
    plan = ResearchPlan.model_validate(raw_plan_stage.get("plan") or {})
    query = str(raw_plan_stage.get("query") or "")
    model_alias = str(raw_plan_stage.get("model_alias") or "local-fast")
    model_budget_usd = str(raw_plan_stage.get("model_budget_usd") or "0")
    planner_uses_model = bool(raw_plan_stage.get("planner_uses_model"))
    synthesis_estimated_cost_usd = str(
        raw_plan_stage.get("synthesis_estimated_cost_usd") or "0"
    )

    raw_context_pack = payload.get("research_context_pack")
    context_pack = raw_context_pack if isinstance(raw_context_pack, dict) else {"items": []}
    context_evidence = context_pack_model_records(context_pack)
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for slot, call in enumerate(plan.calls):
            completed_slots = [int(item["slot"]) for item in results]
            _heartbeat_tool_progress(
                phase="tool-start",
                planned_tool_calls=len(plan.calls),
                active_slot=slot,
                completed_slots=completed_slots,
            )
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
            invocation_id = str(start.json()["invocation_id"])

            deadline = asyncio.get_running_loop().time() + 300.0
            while True:
                _heartbeat_tool_progress(
                    phase="tool-wait",
                    planned_tool_calls=len(plan.calls),
                    active_slot=slot,
                    completed_slots=completed_slots,
                )
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
                    completed_slots = [int(item["slot"]) for item in results]
                    _heartbeat_tool_progress(
                        phase="tool-completed",
                        planned_tool_calls=len(plan.calls),
                        active_slot=slot,
                        completed_slots=completed_slots,
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

    tool_evidence = build_research_evidence(results)
    evidence = [*context_evidence, *tool_evidence]
    context_summary = {
        "sources": context_pack.get("sources") if isinstance(context_pack.get("sources"), dict) else {},
        "item_count": int(context_pack.get("item_count") or len(context_evidence)),
        "character_count": int(context_pack.get("character_count") or 0),
        "max_character_count": int(context_pack.get("max_character_count") or 0),
    }
    return {
        "query": query,
        "model_alias": model_alias,
        "model_budget_usd": model_budget_usd,
        "planner_uses_model": planner_uses_model,
        "synthesis_estimated_cost_usd": synthesis_estimated_cost_usd,
        "plan": plan.model_dump(mode="json"),
        "tool_results": results,
        "evidence": evidence,
        "context_pack": context_summary,
    }


@activity.defn(name="synthesize_research_stage")
async def synthesize_research_stage(payload: dict[str, Any]) -> dict[str, Any]:
    """Ground the final answer from the durable evidence stage and return the canonical artifact body."""

    task_id = str(payload["task_id"])
    execution_id = str(payload.get("workflow_execution_id") or "") or None
    correlation_id = str(payload.get("correlation_id") or "") or None
    raw_evidence_stage = payload.get("research_evidence_stage")
    if not isinstance(raw_evidence_stage, dict):
        raise ApplicationError("Research evidence stage is missing", non_retryable=True)

    query = str(raw_evidence_stage.get("query") or "")
    model_alias = str(raw_evidence_stage.get("model_alias") or "local-fast")
    model_budget_usd = str(raw_evidence_stage.get("model_budget_usd") or "0")
    planner_uses_model = bool(raw_evidence_stage.get("planner_uses_model"))
    plan = ResearchPlan.model_validate(raw_evidence_stage.get("plan") or {})
    results = (
        raw_evidence_stage.get("tool_results")
        if isinstance(raw_evidence_stage.get("tool_results"), list)
        else []
    )
    evidence = (
        raw_evidence_stage.get("evidence")
        if isinstance(raw_evidence_stage.get("evidence"), list)
        else []
    )
    context_summary = (
        raw_evidence_stage.get("context_pack")
        if isinstance(raw_evidence_stage.get("context_pack"), dict)
        else {}
    )

    if evidence:
        model_checkpoints = ModelCheckpointLedger.from_activity()
        synthesis_call_key = deterministic_model_call_key(
            task_id=task_id,
            workflow_execution_id=execution_id,
            call_slot="research-synthesis-v1",
        )
        synthesis_estimated_cost = Decimal(
            str(raw_evidence_stage.get("synthesis_estimated_cost_usd") or "0")
        )

        async def accounted_synthesis_completion(messages: list[dict[str, Any]]) -> str:
            result = await chat_completion(
                task_id=task_id,
                workflow_execution_id=execution_id,
                correlation_id=correlation_id,
                model_alias=model_alias,
                messages=messages,
                idempotency_key=synthesis_call_key,
                checkpoint_ledger=model_checkpoints,
                temperature=0.0,
                estimated_cost_usd=synthesis_estimated_cost,
                timeout_seconds=60.0,
            )
            return result.content

        try:
            synthesis = await synthesize_research(
                query=query,
                evidence=evidence,
                completion=accounted_synthesis_completion,
            )
        except UnexpectedModelBehavior as exc:
            raise ApplicationError(
                f"Research synthesizer produced invalid grounded output: {str(exc)[:1000]}",
                non_retryable=True,
            ) from exc
    else:
        synthesis = no_evidence_synthesis()

    return {
        "kind": "autonomous-research",
        "title": f"Research — {query}"[:320],
        "content": {
            "query": query,
            "answer": synthesis.answer,
            "synthesis": synthesis.model_dump(mode="json"),
            "evidence": build_evidence_index(evidence),
            "context_pack": context_summary,
            "planner_model_alias": model_alias if planner_uses_model else None,
            "synthesis_model_alias": model_alias if evidence else None,
            "model_budget_usd": model_budget_usd,
            "plan": plan.model_dump(mode="json"),
            "tool_results": results,
            "tool_call_count": len(results),
            "authority": "canonical-context-derived-context-read-only-a1-policy-bound-child-tasks",
        },
    }
