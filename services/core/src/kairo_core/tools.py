from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_admin, require_kairo_user
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Project, Task, WorkflowExecution
from .security import require_internal_token
from .tool_models import ToolDefinition, ToolInvocation, ToolServer

router = APIRouter()


class ToolServerCreate(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    namespace: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    title: str = Field(min_length=1, max_length=240)
    endpoint_url: str = Field(min_length=1, max_length=2048)
    transport: Literal["mcp_streamable_http"] = "mcp_streamable_http"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolServerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    namespace: str
    title: str
    transport: str
    endpoint_url: str
    enabled: bool
    catalog_generation: int
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ToolCatalogItem(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    title: str | None = Field(default=None, max_length=240)
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] = Field(default_factory=dict)


class ToolCatalogSync(BaseModel):
    tools: list[ToolCatalogItem] = Field(default_factory=list, max_length=1000)


class ToolDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    server_id: uuid.UUID
    key: str
    remote_name: str
    title: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    remote_annotations: dict[str, Any]
    schema_hash: str
    available: bool
    enabled: bool
    authority_level: int
    estimated_cost_usd: Decimal
    risk_class: str
    retry_policy: str
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ToolPolicyUpdate(BaseModel):
    enabled: bool | None = None
    authority_level: int | None = Field(default=None, ge=1, le=10)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    risk_class: Literal["read", "write", "destructive"] | None = None
    retry_policy: Literal["safe_retry", "no_retry"] | None = None


class ToolInvocationCreate(BaseModel):
    project_id: uuid.UUID
    tool_key: str = Field(min_length=1, max_length=200)
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class ToolInvocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_definition_id: uuid.UUID
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None
    idempotency_key: str
    correlation_id: uuid.UUID
    authority_level: int
    estimated_cost_usd: Decimal
    status: str
    input_json: dict[str, Any]
    result_json: dict[str, Any]
    last_error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ToolInvocationCreated(BaseModel):
    invocation: ToolInvocationRead
    task_id: uuid.UUID


class ToolInvocationContext(BaseModel):
    invocation_id: uuid.UUID
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None
    status: str
    tool_key: str
    remote_name: str
    endpoint_url: str
    transport: str
    input: dict[str, Any]
    retry_policy: str
    authority_level: int
    estimated_cost_usd: Decimal
    result: dict[str, Any] = Field(default_factory=dict)


class ToolInvocationComplete(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)


class ToolInvocationFail(BaseModel):
    error: str = Field(min_length=1, max_length=4000)


def _schema_hash(item: ToolCatalogItem) -> str:
    payload = {
        "name": item.name,
        "input_schema": item.input_schema,
        "output_schema": item.output_schema,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _risk_defaults(annotations: dict[str, Any]) -> tuple[str, int, str]:
    """Treat remote annotations only as hints; unknown tools default to write/no-retry/A2."""
    read_only = bool(annotations.get("readOnlyHint"))
    destructive = bool(annotations.get("destructiveHint"))
    idempotent = bool(annotations.get("idempotentHint"))
    if destructive:
        return "destructive", 3, "no_retry"
    if read_only:
        return "read", 1, "safe_retry"
    return "write", 2, "safe_retry" if idempotent else "no_retry"


@router.post("/v1/tool-servers", response_model=ToolServerRead, status_code=status.HTTP_201_CREATED)
async def create_tool_server(
    body: ToolServerCreate,
    principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> ToolServer:
    existing = await session.scalar(
        select(ToolServer).where((ToolServer.key == body.key) | (ToolServer.namespace == body.namespace))
    )
    if existing:
        raise HTTPException(status_code=409, detail="Tool server key or namespace already exists")
    if not body.endpoint_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="Only HTTP(S) MCP endpoints are supported")
    server = ToolServer(
        key=body.key,
        namespace=body.namespace,
        title=body.title,
        transport=body.transport,
        endpoint_url=body.endpoint_url,
        metadata_json=body.metadata,
    )
    session.add(server)
    await session.flush()
    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="tool.server.created",
        aggregate_type="tool_server",
        aggregate_id=server.id,
        correlation_id=correlation_id,
        payload={"tool_server_id": str(server.id), "key": server.key, "namespace": server.namespace},
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="tool.server.create",
        resource_type="tool_server",
        resource_id=str(server.id),
        authority_level=2,
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(server)
    return server


@router.get("/v1/tool-servers", response_model=list[ToolServerRead])
async def list_tool_servers(
    _: Principal = Depends(require_kairo_user), session: AsyncSession = Depends(get_session)
) -> list[ToolServer]:
    rows = await session.execute(select(ToolServer).order_by(ToolServer.key))
    return list(rows.scalars())


@router.post(
    "/internal/v1/tool-servers/{server_id}/catalog",
    response_model=list[ToolDefinitionRead],
    dependencies=[Depends(require_internal_token)],
)
async def sync_tool_catalog(
    server_id: uuid.UUID,
    body: ToolCatalogSync,
    session: AsyncSession = Depends(get_session),
) -> list[ToolDefinition]:
    server = await session.get(ToolServer, server_id, with_for_update=True)
    if not server:
        raise HTTPException(status_code=404, detail="Tool server not found")
    now = datetime.now(UTC)
    seen_names: set[str] = set()
    synced: list[ToolDefinition] = []
    for item in body.tools:
        if item.name in seen_names:
            raise HTTPException(status_code=422, detail=f"Duplicate remote tool name: {item.name}")
        seen_names.add(item.name)
        definition = await session.scalar(
            select(ToolDefinition).where(
                ToolDefinition.server_id == server.id,
                ToolDefinition.remote_name == item.name,
            )
        )
        risk_class, authority_level, retry_policy = _risk_defaults(item.annotations)
        key = f"{server.namespace}.{item.name}"
        schema_hash = _schema_hash(item)
        if definition is None:
            definition = ToolDefinition(
                server_id=server.id,
                key=key,
                remote_name=item.name,
                title=item.title or item.name,
                description=item.description,
                input_schema=item.input_schema,
                output_schema=item.output_schema,
                remote_annotations=item.annotations,
                schema_hash=schema_hash,
                available=True,
                enabled=False,
                authority_level=authority_level,
                estimated_cost_usd=Decimal("0"),
                risk_class=risk_class,
                retry_policy=retry_policy,
                last_seen_at=now,
            )
            session.add(definition)
        else:
            definition.title = item.title or item.name
            definition.description = item.description
            definition.input_schema = item.input_schema
            definition.output_schema = item.output_schema
            definition.remote_annotations = item.annotations
            definition.schema_hash = schema_hash
            definition.available = True
            definition.last_seen_at = now
        synced.append(definition)

    existing_rows = await session.execute(select(ToolDefinition).where(ToolDefinition.server_id == server.id))
    for definition in existing_rows.scalars():
        if definition.remote_name not in seen_names:
            definition.available = False

    server.catalog_generation += 1
    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="tool.catalog.synced",
        aggregate_type="tool_server",
        aggregate_id=server.id,
        correlation_id=correlation_id,
        payload={
            "tool_server_id": str(server.id),
            "generation": server.catalog_generation,
            "tool_count": len(synced),
        },
    )
    await session.commit()
    for definition in synced:
        await session.refresh(definition)
    return synced


@router.get("/v1/tools", response_model=list[ToolDefinitionRead])
async def list_tools(
    enabled_only: bool = False,
    _: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[ToolDefinition]:
    statement = select(ToolDefinition).order_by(ToolDefinition.key)
    if enabled_only:
        statement = statement.where(ToolDefinition.enabled.is_(True), ToolDefinition.available.is_(True))
    rows = await session.execute(statement)
    return list(rows.scalars())


@router.patch("/v1/tools/{tool_key}/policy", response_model=ToolDefinitionRead)
async def update_tool_policy(
    tool_key: str,
    body: ToolPolicyUpdate,
    principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> ToolDefinition:
    tool = await session.scalar(
        select(ToolDefinition).where(ToolDefinition.key == tool_key).with_for_update()
    )
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if body.enabled is True and not tool.available:
        raise HTTPException(status_code=409, detail="Unavailable tool cannot be enabled")
    updates = body.model_dump(exclude_none=True)
    for field_name, value in updates.items():
        setattr(tool, field_name, value)
    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="tool.policy.updated",
        aggregate_type="tool_definition",
        aggregate_id=tool.id,
        correlation_id=correlation_id,
        payload={"tool_key": tool.key, **{k: str(v) for k, v in updates.items()}},
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="tool.policy.update",
        resource_type="tool_definition",
        resource_id=str(tool.id),
        authority_level=max(1, int(tool.authority_level)),
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json", exclude_none=True),
    )
    await session.commit()
    await session.refresh(tool)
    return tool


@router.post("/v1/tool-invocations", response_model=ToolInvocationCreated, status_code=status.HTTP_201_CREATED)
async def create_tool_invocation(
    body: ToolInvocationCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> ToolInvocationCreated:
    project = await session.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    tool = await session.scalar(select(ToolDefinition).where(ToolDefinition.key == body.tool_key))
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    server = await session.get(ToolServer, tool.server_id)
    if not server or not server.enabled or not tool.available or not tool.enabled:
        raise HTTPException(status_code=409, detail="Tool is not enabled and available")

    invocation_id = uuid.uuid4()
    idempotency_key = body.idempotency_key or str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:tool:{invocation_id}:{tool.key}")
    )
    existing = await session.scalar(
        select(ToolInvocation).where(ToolInvocation.idempotency_key == idempotency_key)
    )
    if existing:
        if existing.tool_definition_id != tool.id or existing.input_json != body.input:
            raise HTTPException(status_code=409, detail="Idempotency key is already bound to another invocation")
        return ToolInvocationCreated(invocation=ToolInvocationRead.model_validate(existing), task_id=existing.task_id)

    correlation_id = uuid.uuid4()
    task = Task(
        project_id=project.id,
        title=f"Invoke {tool.key}",
        description=tool.description,
        status="todo",
        owner_type="agent",
        owner_ref="kairo.tool-runtime",
        authority_ceiling=tool.authority_level,
        budget_usd=tool.estimated_cost_usd,
        input={
            "capability": "tool.invoke",
            "tool_invocation_id": str(invocation_id),
            "tool_key": tool.key,
            "authority_level": tool.authority_level,
            "estimated_cost_usd": str(tool.estimated_cost_usd),
            "policy_scope": {
                "tool_key": tool.key,
                "risk_class": tool.risk_class,
                "server_key": server.key,
            },
            "approval_reason": f"KAIRO requests MCP tool {tool.key} ({tool.risk_class})",
        },
    )
    session.add(task)
    await session.flush()
    invocation = ToolInvocation(
        id=invocation_id,
        tool_definition_id=tool.id,
        task_id=task.id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        authority_level=tool.authority_level,
        estimated_cost_usd=tool.estimated_cost_usd,
        status="pending",
        input_json=body.input,
    )
    session.add(invocation)
    await session.flush()
    await enqueue_domain_event(
        session,
        event_type="tool.invocation.created",
        aggregate_type="tool_invocation",
        aggregate_id=invocation.id,
        correlation_id=correlation_id,
        payload={"invocation_id": str(invocation.id), "task_id": str(task.id), "tool_key": tool.key},
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="tool.invoke.request",
        resource_type="tool_definition",
        resource_id=tool.key,
        authority_level=tool.authority_level,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_json={"project_id": str(project.id), "tool_key": tool.key, "input": body.input},
    )
    await session.commit()
    await session.refresh(invocation)
    return ToolInvocationCreated(invocation=ToolInvocationRead.model_validate(invocation), task_id=task.id)


@router.get("/v1/tool-invocations/{invocation_id}", response_model=ToolInvocationRead)
async def get_tool_invocation(
    invocation_id: uuid.UUID,
    _: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> ToolInvocation:
    invocation = await session.get(ToolInvocation, invocation_id)
    if not invocation:
        raise HTTPException(status_code=404, detail="Tool invocation not found")
    return invocation


@router.get(
    "/internal/v1/tool-invocations/{invocation_id}/context",
    response_model=ToolInvocationContext,
    dependencies=[Depends(require_internal_token)],
)
async def tool_invocation_context(
    invocation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ToolInvocationContext:
    invocation = await session.get(ToolInvocation, invocation_id)
    if not invocation:
        raise HTTPException(status_code=404, detail="Tool invocation not found")
    tool = await session.get(ToolDefinition, invocation.tool_definition_id)
    server = await session.get(ToolServer, tool.server_id) if tool else None
    if not tool or not server:
        raise HTTPException(status_code=409, detail="Tool registry entry is incomplete")
    return ToolInvocationContext(
        invocation_id=invocation.id,
        task_id=invocation.task_id,
        workflow_execution_id=invocation.workflow_execution_id,
        status=invocation.status,
        tool_key=tool.key,
        remote_name=tool.remote_name,
        endpoint_url=server.endpoint_url,
        transport=server.transport,
        input=invocation.input_json,
        retry_policy=tool.retry_policy,
        authority_level=invocation.authority_level,
        estimated_cost_usd=invocation.estimated_cost_usd,
        result=invocation.result_json,
    )


@router.post(
    "/internal/v1/tool-invocations/{invocation_id}/start",
    response_model=ToolInvocationRead,
    dependencies=[Depends(require_internal_token)],
)
async def start_tool_invocation(
    invocation_id: uuid.UUID,
    workflow_execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ToolInvocation:
    invocation = await session.get(ToolInvocation, invocation_id, with_for_update=True)
    if not invocation:
        raise HTTPException(status_code=404, detail="Tool invocation not found")
    execution = await session.get(WorkflowExecution, workflow_execution_id)
    if not execution or execution.task_id != invocation.task_id:
        raise HTTPException(status_code=409, detail="Workflow execution does not belong to invocation task")
    if invocation.status == "completed":
        return invocation
    invocation.workflow_execution_id = execution.id
    invocation.status = "running"
    invocation.started_at = invocation.started_at or datetime.now(UTC)
    await session.commit()
    await session.refresh(invocation)
    return invocation


@router.post(
    "/internal/v1/tool-invocations/{invocation_id}/complete",
    response_model=ToolInvocationRead,
    dependencies=[Depends(require_internal_token)],
)
async def complete_tool_invocation(
    invocation_id: uuid.UUID,
    body: ToolInvocationComplete,
    session: AsyncSession = Depends(get_session),
) -> ToolInvocation:
    invocation = await session.get(ToolInvocation, invocation_id, with_for_update=True)
    if not invocation:
        raise HTTPException(status_code=404, detail="Tool invocation not found")
    if invocation.status == "completed":
        if invocation.result_json != body.result:
            raise HTTPException(status_code=409, detail="Completed invocation result cannot be rebound")
        return invocation
    invocation.status = "completed"
    invocation.result_json = body.result
    invocation.last_error = None
    invocation.completed_at = datetime.now(UTC)
    await enqueue_domain_event(
        session,
        event_type="tool.invocation.completed",
        aggregate_type="tool_invocation",
        aggregate_id=invocation.id,
        correlation_id=invocation.correlation_id,
        payload={"invocation_id": str(invocation.id), "task_id": str(invocation.task_id)},
    )
    await append_audit(
        session,
        actor_type="worker",
        actor_id=str(invocation.workflow_execution_id) if invocation.workflow_execution_id else None,
        action="tool.invoke.complete",
        resource_type="tool_invocation",
        resource_id=str(invocation.id),
        authority_level=invocation.authority_level,
        correlation_id=invocation.correlation_id,
        idempotency_key=f"tool-invocation:{invocation.id}:complete",
        result_json=body.result,
    )
    await session.commit()
    await session.refresh(invocation)
    return invocation


@router.post(
    "/internal/v1/tool-invocations/{invocation_id}/fail",
    response_model=ToolInvocationRead,
    dependencies=[Depends(require_internal_token)],
)
async def fail_tool_invocation(
    invocation_id: uuid.UUID,
    body: ToolInvocationFail,
    session: AsyncSession = Depends(get_session),
) -> ToolInvocation:
    invocation = await session.get(ToolInvocation, invocation_id, with_for_update=True)
    if not invocation:
        raise HTTPException(status_code=404, detail="Tool invocation not found")
    if invocation.status == "completed":
        return invocation
    invocation.status = "failed"
    invocation.last_error = body.error
    invocation.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(invocation)
    return invocation
