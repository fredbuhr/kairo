from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Task, WorkflowExecution
from .project_access import get_owned_project
from .research_context import router as research_context_router
from .schemas import TaskRunResponse
from .security import require_internal_token
from .tool_models import ToolDefinition, ToolInvocation, ToolServer
from .tools import _validate_tool_input
from .workflows import run_task

router = APIRouter()
router.include_router(research_context_router)


class ResearchRunCreate(BaseModel):
    project_id: uuid.UUID
    query: str = Field(min_length=3, max_length=4000)
    max_tool_calls: int = Field(default=3, ge=1, le=8)
    allowed_tool_keys: list[str] = Field(default_factory=list, max_length=32)
    model_alias: str = Field(default="local-fast", min_length=1, max_length=120)
    estimated_model_cost_usd: Decimal = Field(default=Decimal("0.01"), ge=0, le=1)


class ResearchContext(BaseModel):
    task_id: uuid.UUID
    project_id: uuid.UUID
    query: str
    max_tool_calls: int
    model_alias: str
    estimated_model_cost_usd: Decimal
    tools: list[dict[str, Any]]


class ResearchToolRequest(BaseModel):
    tool_key: str = Field(min_length=1, max_length=200)
    input: dict[str, Any] = Field(default_factory=dict)
    slot: int = Field(ge=0, le=31)
    rationale: str | None = Field(default=None, max_length=1000)


class ResearchToolStarted(BaseModel):
    invocation_id: uuid.UUID
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID
    workflow_id: str
    status: str
    already_started: bool


class ResearchToolResult(BaseModel):
    invocation_id: uuid.UUID
    task_id: uuid.UUID
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


def _research_task_input(task: Task) -> dict[str, Any]:
    value = task.input or {}
    if str(value.get("capability") or "") != "research.autonomous":
        raise HTTPException(status_code=409, detail="Task is not an autonomous research task")
    return value


async def _eligible_tools(session: AsyncSession, task_input: dict[str, Any]) -> list[ToolDefinition]:
    requested = {str(key) for key in task_input.get("allowed_tool_keys") or [] if str(key)}
    statement = (
        select(ToolDefinition)
        .join(ToolServer, ToolServer.id == ToolDefinition.server_id)
        .where(
            ToolServer.enabled.is_(True),
            ToolDefinition.available.is_(True),
            ToolDefinition.enabled.is_(True),
            ToolDefinition.risk_class == "read",
            ToolDefinition.authority_level == 1,
        )
        .order_by(ToolDefinition.key)
    )
    if requested:
        statement = statement.where(ToolDefinition.key.in_(requested))
    rows = await session.execute(statement)
    return list(rows.scalars())


async def _terminal_research_tool_response(
    session: AsyncSession, invocation: ToolInvocation
) -> ResearchToolStarted:
    if invocation.workflow_execution_id is None:
        raise HTTPException(status_code=409, detail="Terminal invocation has no workflow execution")
    execution = await session.get(WorkflowExecution, invocation.workflow_execution_id)
    if execution is None:
        raise HTTPException(status_code=409, detail="Tool workflow execution is missing")
    return ResearchToolStarted(
        invocation_id=invocation.id,
        task_id=invocation.task_id,
        workflow_execution_id=execution.id,
        workflow_id=execution.workflow_id,
        status=invocation.status,
        already_started=True,
    )


@router.post("/v1/research/runs", response_model=TaskRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_research_run(
    body: ResearchRunCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> TaskRunResponse:
    project = await get_owned_project(session, body.project_id, principal)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    correlation_id = uuid.uuid4()
    task = Task(
        project_id=project.id,
        title=f"Research — {body.query}"[:320],
        description="Autonomous read-only research through explicitly enabled KAIRO MCP tools.",
        status="todo",
        owner_type="agent",
        owner_ref="kairo.research-agent",
        authority_ceiling=1,
        budget_usd=body.estimated_model_cost_usd,
        input={
            "capability": "research.autonomous",
            "query": body.query,
            "requester_subject": principal.subject,
            "max_tool_calls": body.max_tool_calls,
            "allowed_tool_keys": body.allowed_tool_keys,
            "model_alias": body.model_alias,
            "estimated_model_cost_usd": str(body.estimated_model_cost_usd),
            "authority_level": 1,
            "estimated_cost_usd": str(body.estimated_model_cost_usd),
            "policy_scope": {"capability": "research.autonomous", "tool_risk_ceiling": "read"},
            "approval_reason": "KAIRO requests a bounded read-only autonomous research run",
        },
    )
    session.add(task)
    await session.flush()
    await enqueue_domain_event(
        session,
        event_type="research.requested",
        aggregate_type="task",
        aggregate_id=task.id,
        correlation_id=correlation_id,
        payload={"task_id": str(task.id), "project_id": str(project.id), "query": body.query},
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="research.autonomous.request",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json"),
    )
    await session.commit()
    return await run_task(task.id, session)


@router.get(
    "/internal/v1/research/tasks/{task_id}/context",
    response_model=ResearchContext,
    dependencies=[Depends(require_internal_token)],
)
async def research_context(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> ResearchContext:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Research task not found")
    task_input = _research_task_input(task)
    tools = await _eligible_tools(session, task_input)
    return ResearchContext(
        task_id=task.id,
        project_id=task.project_id,
        query=str(task_input.get("query") or ""),
        max_tool_calls=int(task_input.get("max_tool_calls") or 3),
        model_alias=str(task_input.get("model_alias") or "local-fast"),
        estimated_model_cost_usd=Decimal(str(task_input.get("estimated_model_cost_usd") or "0.01")),
        tools=[
            {
                "key": tool.key,
                "title": tool.title,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "schema_hash": tool.schema_hash,
            }
            for tool in tools
        ],
    )


@router.post(
    "/internal/v1/research/tasks/{task_id}/tool-invocations",
    response_model=ResearchToolStarted,
    dependencies=[Depends(require_internal_token)],
)
async def start_research_tool(
    task_id: uuid.UUID,
    body: ResearchToolRequest,
    session: AsyncSession = Depends(get_session),
) -> ResearchToolStarted:
    parent = await session.get(Task, task_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Research task not found")
    task_input = _research_task_input(parent)
    max_calls = int(task_input.get("max_tool_calls") or 3)
    if body.slot >= max_calls:
        raise HTTPException(status_code=422, detail="Research tool slot exceeds task budget")

    eligible = {tool.key: tool for tool in await _eligible_tools(session, task_input)}
    tool = eligible.get(body.tool_key)
    if tool is None:
        raise HTTPException(
            status_code=409,
            detail="Research agent may only invoke explicitly enabled read-only A1 tools",
        )
    _validate_tool_input(tool.input_schema, body.input)
    server = await session.get(ToolServer, tool.server_id)
    if server is None:
        raise HTTPException(status_code=409, detail="Tool server binding is missing")

    invocation_id = uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:research:{parent.id}:slot:{body.slot}:{tool.key}")
    idempotency_key = f"research:{parent.id}:{body.slot}:{tool.key}"
    existing = await session.scalar(
        select(ToolInvocation).where(ToolInvocation.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.tool_definition_id != tool.id or existing.input_json != body.input:
            raise HTTPException(status_code=409, detail="Research tool slot is already bound to another call")
        if existing.status in {"completed", "failed"}:
            return await _terminal_research_tool_response(session, existing)
        run = await run_task(existing.task_id, session)
        return ResearchToolStarted(
            invocation_id=existing.id,
            task_id=existing.task_id,
            workflow_execution_id=run.workflow_execution_id,
            workflow_id=run.workflow_id,
            status=run.status,
            already_started=run.already_started,
        )

    child_task_id = uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:research-tool-task:{invocation_id}")
    correlation_id = uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:research-tool-correlation:{invocation_id}")
    child = Task(
        id=child_task_id,
        project_id=parent.project_id,
        title=f"Research tool — {tool.key}"[:320],
        description=body.rationale or tool.description,
        status="todo",
        owner_type="agent",
        owner_ref="kairo.research-agent",
        authority_ceiling=1,
        budget_usd=tool.estimated_cost_usd,
        input={
            "capability": "tool.invoke",
            "tool_invocation_id": str(invocation_id),
            "tool_key": tool.key,
            "tool_schema_hash": tool.schema_hash,
            "authority_level": 1,
            "estimated_cost_usd": str(tool.estimated_cost_usd),
            "policy_scope": {
                "tool_key": tool.key,
                "risk_class": "read",
                "retry_policy": tool.retry_policy,
                "server_key": server.key,
                "research_parent_task_id": str(parent.id),
            },
            "approval_reason": f"Research agent requests read-only MCP tool {tool.key}",
        },
    )
    session.add(child)
    await session.flush()
    invocation = ToolInvocation(
        id=invocation_id,
        tool_definition_id=tool.id,
        task_id=child.id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        authority_level=1,
        estimated_cost_usd=tool.estimated_cost_usd,
        status="pending",
        input_json=body.input,
    )
    session.add(invocation)
    await enqueue_domain_event(
        session,
        event_type="research.tool.requested",
        aggregate_type="tool_invocation",
        aggregate_id=invocation.id,
        correlation_id=correlation_id,
        payload={
            "research_task_id": str(parent.id),
            "tool_key": tool.key,
            "slot": body.slot,
            "tool_task_id": str(child.id),
        },
    )
    await append_audit(
        session,
        actor_type="agent",
        actor_id="kairo.research-agent",
        action="research.tool.request",
        resource_type="tool_definition",
        resource_id=tool.key,
        authority_level=1,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_json={"parent_task_id": str(parent.id), "slot": body.slot, "input": body.input},
    )
    await session.commit()
    run = await run_task(child.id, session)
    return ResearchToolStarted(
        invocation_id=invocation.id,
        task_id=child.id,
        workflow_execution_id=run.workflow_execution_id,
        workflow_id=run.workflow_id,
        status=run.status,
        already_started=run.already_started,
    )


@router.get(
    "/internal/v1/research/tool-invocations/{invocation_id}",
    response_model=ResearchToolResult,
    dependencies=[Depends(require_internal_token)],
)
async def research_tool_result(
    invocation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ResearchToolResult:
    invocation = await session.get(ToolInvocation, invocation_id)
    if invocation is None:
        raise HTTPException(status_code=404, detail="Tool invocation not found")
    task = await session.get(Task, invocation.task_id)
    scope = (task.input or {}).get("policy_scope") if task else None
    if not isinstance(scope, dict) or not scope.get("research_parent_task_id"):
        raise HTTPException(status_code=409, detail="Invocation does not belong to a research agent")
    return ResearchToolResult(
        invocation_id=invocation.id,
        task_id=invocation.task_id,
        status=invocation.status,
        result=invocation.result_json or {},
        error=invocation.last_error,
    )
