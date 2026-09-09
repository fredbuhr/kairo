from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_admin, require_kairo_user
from .automation_models import AutomationDefinition, AutomationInvocation
from .config import settings
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Project, SecretReference, Task, WorkflowExecution
from .openbao import openbao_client
from .security import require_internal_token
from .workflows import run_task


router = APIRouter(tags=["automations"])

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_SECRET_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class AutomationCreate(BaseModel):
    project_id: uuid.UUID
    key: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=240)
    description: str | None = None
    engine: Literal["activepieces_webhook"] = "activepieces_webhook"
    authority_level: int = Field(default=2, ge=1, le=10)
    webhook_secret_reference_id: uuid.UUID
    webhook_secret_key: str = Field(default="path", min_length=1, max_length=120)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self) -> "AutomationCreate":
        self.key = self.key.strip().lower()
        self.name = self.name.strip()
        self.webhook_secret_key = self.webhook_secret_key.strip()
        if not _KEY_PATTERN.fullmatch(self.key):
            raise ValueError("automation key must use lowercase letters, digits, dots, underscores or hyphens")
        if not _SECRET_KEY_PATTERN.fullmatch(self.webhook_secret_key):
            raise ValueError("webhook secret key contains unsupported characters")
        return self


class AutomationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    enabled: bool | None = None
    authority_level: int | None = Field(default=None, ge=1, le=10)
    webhook_secret_reference_id: uuid.UUID | None = None
    webhook_secret_key: str | None = Field(default=None, min_length=1, max_length=120)
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def normalize(self) -> "AutomationUpdate":
        if self.name is not None:
            self.name = self.name.strip()
        if self.webhook_secret_key is not None:
            self.webhook_secret_key = self.webhook_secret_key.strip()
            if not _SECRET_KEY_PATTERN.fullmatch(self.webhook_secret_key):
                raise ValueError("webhook secret key contains unsupported characters")
        return self


class AutomationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    key: str
    name: str
    description: str | None
    engine: str
    enabled: bool
    authority_level: int
    webhook_secret_reference_id: uuid.UUID
    webhook_secret_key: str
    timeout_seconds: int
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AutomationRunCreate(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=240)


class AutomationInvocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    automation_id: uuid.UUID
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None
    idempotency_key: str
    correlation_id: uuid.UUID
    status: str
    input_json: dict[str, Any]
    result_json: dict[str, Any]
    response_status: int | None
    outcome_ambiguous: bool
    last_error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AutomationRunCreated(BaseModel):
    invocation: AutomationInvocationRead
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None = None
    workflow_status: str | None = None


class InternalAutomationContext(BaseModel):
    invocation_id: uuid.UUID
    automation_id: uuid.UUID
    task_id: uuid.UUID
    engine: Literal["activepieces_webhook"]
    endpoint_url: str
    timeout_seconds: int
    input: dict[str, Any]
    correlation_id: uuid.UUID


class InternalAutomationStart(BaseModel):
    workflow_execution_id: uuid.UUID


class InternalAutomationComplete(BaseModel):
    response_status: int = Field(ge=100, le=599)
    result: dict[str, Any] = Field(default_factory=dict)


class InternalAutomationFail(BaseModel):
    error: str = Field(min_length=1, max_length=4000)
    response_status: int | None = Field(default=None, ge=100, le=599)
    outcome_ambiguous: bool = False
    result: dict[str, Any] = Field(default_factory=dict)


async def _automation_owned(
    automation_id: uuid.UUID,
    principal: Principal,
    session: AsyncSession,
    *,
    lock: bool = False,
) -> AutomationDefinition:
    statement = select(AutomationDefinition).where(
        AutomationDefinition.id == automation_id,
        AutomationDefinition.keycloak_subject == principal.subject,
    )
    if lock:
        statement = statement.with_for_update()
    automation = await session.scalar(statement)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    return automation


async def _secret_reference(reference_id: uuid.UUID, session: AsyncSession) -> SecretReference:
    reference = await session.get(SecretReference, reference_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="Secret reference not found")
    return reference


async def _validate_secret_binding(
    reference_id: uuid.UUID,
    key: str,
    session: AsyncSession,
) -> None:
    reference = await _secret_reference(reference_id, session)
    try:
        provider_status = await openbao_client.secret_status(reference.provider_path)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenBao is unavailable or rejected the automation secret reference",
        ) from exc
    if not provider_status.exists:
        raise HTTPException(status_code=409, detail="Automation secret does not exist in OpenBao")
    if key not in provider_status.keys:
        raise HTTPException(status_code=409, detail="Automation webhook secret key is missing")


def _activepieces_endpoint(secret_path: str) -> str:
    path = secret_path.strip()
    if not path or len(path) > 4096:
        raise ValueError("Activepieces webhook path is empty or too long")
    if "://" in path or path.startswith("//") or "\\" in path:
        raise ValueError("Activepieces webhook secret must contain a path, not an arbitrary URL")
    if any(ord(character) < 32 for character in path):
        raise ValueError("Activepieces webhook path contains control characters")
    return f"{settings.activepieces_url.rstrip('/')}/{path.lstrip('/')}"


async def _internal_invocation(
    invocation_id: uuid.UUID,
    session: AsyncSession,
    *,
    lock: bool = False,
) -> tuple[AutomationInvocation, AutomationDefinition, Task]:
    statement = select(AutomationInvocation).where(AutomationInvocation.id == invocation_id)
    if lock:
        statement = statement.with_for_update()
    invocation = await session.scalar(statement)
    if invocation is None:
        raise HTTPException(status_code=404, detail="Automation invocation not found")
    automation = await session.get(AutomationDefinition, invocation.automation_id)
    task = await session.get(Task, invocation.task_id)
    if automation is None or task is None:
        raise HTTPException(status_code=409, detail="Automation invocation binding is incomplete")
    task_input = task.input or {}
    if (
        str(task_input.get("automation_id") or "") != str(automation.id)
        or str(task_input.get("automation_invocation_id") or "") != str(invocation.id)
        or str(task_input.get("capability") or "") != "automation.invoke"
    ):
        raise HTTPException(status_code=409, detail="Automation invocation task binding is stale")
    return invocation, automation, task


@router.post("/v1/automations", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
async def create_automation(
    body: AutomationCreate,
    principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> AutomationDefinition:
    project = await session.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await _secret_reference(body.webhook_secret_reference_id, session)

    automation = AutomationDefinition(
        keycloak_subject=principal.subject,
        project_id=body.project_id,
        key=body.key,
        name=body.name,
        description=body.description,
        engine=body.engine,
        enabled=False,
        authority_level=body.authority_level,
        webhook_secret_reference_id=body.webhook_secret_reference_id,
        webhook_secret_key=body.webhook_secret_key,
        timeout_seconds=body.timeout_seconds,
        metadata_json=body.metadata,
    )
    session.add(automation)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Automation key already exists for this user") from exc

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="automation.created",
        aggregate_type="automation",
        aggregate_id=automation.id,
        correlation_id=correlation_id,
        payload={
            "automation_id": str(automation.id),
            "project_id": str(automation.project_id),
            "key": automation.key,
            "engine": automation.engine,
            "enabled": False,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="automation.create",
        resource_type="automation",
        resource_id=str(automation.id),
        authority_level=2,
        correlation_id=correlation_id,
        request_json={
            "project_id": str(automation.project_id),
            "key": automation.key,
            "engine": automation.engine,
            "authority_level": automation.authority_level,
            "webhook_secret_reference_id": str(automation.webhook_secret_reference_id),
            "webhook_secret_key": automation.webhook_secret_key,
            "timeout_seconds": automation.timeout_seconds,
        },
    )
    await session.commit()
    await session.refresh(automation)
    return automation


@router.get("/v1/automations", response_model=list[AutomationRead])
async def list_automations(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[AutomationDefinition]:
    rows = await session.execute(
        select(AutomationDefinition)
        .where(AutomationDefinition.keycloak_subject == principal.subject)
        .order_by(AutomationDefinition.created_at.desc())
    )
    return list(rows.scalars())


@router.patch("/v1/automations/{automation_id}", response_model=AutomationRead)
async def update_automation(
    automation_id: uuid.UUID,
    body: AutomationUpdate,
    principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> AutomationDefinition:
    automation = await _automation_owned(automation_id, principal, session, lock=True)
    fields = body.model_fields_set
    if not fields:
        return automation

    next_reference_id = (
        body.webhook_secret_reference_id
        if "webhook_secret_reference_id" in fields and body.webhook_secret_reference_id is not None
        else automation.webhook_secret_reference_id
    )
    next_secret_key = (
        body.webhook_secret_key
        if "webhook_secret_key" in fields and body.webhook_secret_key is not None
        else automation.webhook_secret_key
    )
    next_enabled = (
        body.enabled
        if "enabled" in fields and body.enabled is not None
        else automation.enabled
    )
    await _secret_reference(next_reference_id, session)

    # Changing a secret reference/key on an already enabled automation must be just as strict as
    # enabling it for the first time. Otherwise the UI could leave an apparently active definition
    # bound to an invalid webhook until the Worker eventually failed at execution time.
    if next_enabled:
        await _validate_secret_binding(next_reference_id, next_secret_key, session)

    if "name" in fields and body.name is not None:
        automation.name = body.name
    if "description" in fields:
        automation.description = body.description
    if "enabled" in fields and body.enabled is not None:
        automation.enabled = body.enabled
    if "authority_level" in fields and body.authority_level is not None:
        automation.authority_level = body.authority_level
    if "webhook_secret_reference_id" in fields and body.webhook_secret_reference_id is not None:
        automation.webhook_secret_reference_id = body.webhook_secret_reference_id
    if "webhook_secret_key" in fields and body.webhook_secret_key is not None:
        automation.webhook_secret_key = body.webhook_secret_key
    if "timeout_seconds" in fields and body.timeout_seconds is not None:
        automation.timeout_seconds = body.timeout_seconds
    if "metadata" in fields and body.metadata is not None:
        automation.metadata_json = body.metadata

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="automation.updated",
        aggregate_type="automation",
        aggregate_id=automation.id,
        correlation_id=correlation_id,
        payload={
            "automation_id": str(automation.id),
            "enabled": automation.enabled,
            "authority_level": automation.authority_level,
            "changed_fields": sorted(fields),
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="automation.update",
        resource_type="automation",
        resource_id=str(automation.id),
        authority_level=2,
        correlation_id=correlation_id,
        request_json={"changed_fields": sorted(fields)},
    )
    await session.commit()
    await session.refresh(automation)
    return automation


@router.post(
    "/v1/automations/{automation_id}/runs",
    response_model=AutomationRunCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def invoke_automation(
    automation_id: uuid.UUID,
    body: AutomationRunCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> AutomationRunCreated:
    automation = await _automation_owned(automation_id, principal, session)
    if not automation.enabled:
        raise HTTPException(status_code=409, detail="Automation is disabled")

    idempotency_key = body.idempotency_key or str(uuid.uuid4())
    existing = await session.scalar(
        select(AutomationInvocation).where(AutomationInvocation.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.automation_id != automation.id or existing.input_json != body.input:
            raise HTTPException(status_code=409, detail="Idempotency key is bound to another automation request")
        task = await session.get(Task, existing.task_id)
        if task is None:
            raise HTTPException(status_code=409, detail="Automation invocation task is missing")
        if task.status not in {"completed", "failed", "cancelled"}:
            run = await run_task(task.id, session)
            await session.refresh(existing)
            return AutomationRunCreated(
                invocation=AutomationInvocationRead.model_validate(existing),
                task_id=task.id,
                workflow_execution_id=run.workflow_execution_id,
                workflow_status=run.status,
            )
        return AutomationRunCreated(
            invocation=AutomationInvocationRead.model_validate(existing),
            task_id=task.id,
            workflow_execution_id=existing.workflow_execution_id,
            workflow_status=task.status,
        )

    invocation_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    task = Task(
        project_id=automation.project_id,
        title=f"Automation · {automation.name}",
        description=automation.description,
        status="todo",
        owner_type="agent",
        owner_ref="kairo.automation-runtime",
        authority_ceiling=automation.authority_level,
        input={
            "capability": "automation.invoke",
            "automation_id": str(automation.id),
            "automation_invocation_id": str(invocation_id),
            "authority_level": automation.authority_level,
            "estimated_cost_usd": "0",
            "policy_scope": {
                "automation_id": str(automation.id),
                "automation_key": automation.key,
                "engine": automation.engine,
            },
            "approval_reason": f"KAIRO requests automation {automation.key}",
        },
    )
    session.add(task)
    await session.flush()
    invocation = AutomationInvocation(
        id=invocation_id,
        automation_id=automation.id,
        task_id=task.id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        status="pending",
        input_json=body.input,
    )
    session.add(invocation)
    await session.flush()
    await enqueue_domain_event(
        session,
        event_type="automation.invocation.created",
        aggregate_type="automation_invocation",
        aggregate_id=invocation.id,
        correlation_id=correlation_id,
        payload={
            "automation_invocation_id": str(invocation.id),
            "automation_id": str(automation.id),
            "task_id": str(task.id),
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="automation.invoke.request",
        resource_type="automation",
        resource_id=str(automation.id),
        authority_level=automation.authority_level,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        request_json={
            "automation_id": str(automation.id),
            "task_id": str(task.id),
            "input_keys": sorted(body.input),
        },
    )
    await session.commit()
    run = await run_task(task.id, session)
    await session.refresh(invocation)
    return AutomationRunCreated(
        invocation=AutomationInvocationRead.model_validate(invocation),
        task_id=task.id,
        workflow_execution_id=run.workflow_execution_id,
        workflow_status=run.status,
    )


@router.get("/v1/automation-runs", response_model=list[AutomationInvocationRead])
async def list_automation_runs(
    automation_id: uuid.UUID | None = None,
    limit: int = 100,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[AutomationInvocation]:
    statement = (
        select(AutomationInvocation)
        .join(AutomationDefinition, AutomationDefinition.id == AutomationInvocation.automation_id)
        .where(AutomationDefinition.keycloak_subject == principal.subject)
        .order_by(AutomationInvocation.created_at.desc())
        .limit(max(1, min(limit, 250)))
    )
    if automation_id is not None:
        statement = statement.where(AutomationInvocation.automation_id == automation_id)
    rows = await session.execute(statement)
    return list(rows.scalars())


@router.get(
    "/internal/v1/automation-invocations/{invocation_id}/context",
    response_model=InternalAutomationContext,
    dependencies=[Depends(require_internal_token)],
)
async def internal_automation_context(
    invocation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> InternalAutomationContext:
    invocation, automation, _task = await _internal_invocation(invocation_id, session)
    if invocation.status == "completed":
        raise HTTPException(status_code=409, detail="Automation invocation is already completed")
    if invocation.status == "failed":
        raise HTTPException(status_code=409, detail="Automation invocation has failed")
    if not automation.enabled:
        raise HTTPException(status_code=409, detail="Automation authorization is no longer active")

    reference = await _secret_reference(automation.webhook_secret_reference_id, session)
    try:
        secret_path = await openbao_client.read_secret_value(
            reference.provider_path,
            automation.webhook_secret_key,
        )
        endpoint_url = _activepieces_endpoint(secret_path)
    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Automation webhook secret is unavailable or invalid",
        ) from exc

    return InternalAutomationContext(
        invocation_id=invocation.id,
        automation_id=automation.id,
        task_id=invocation.task_id,
        engine="activepieces_webhook",
        endpoint_url=endpoint_url,
        timeout_seconds=automation.timeout_seconds,
        input=dict(invocation.input_json or {}),
        correlation_id=invocation.correlation_id,
    )


@router.post(
    "/internal/v1/automation-invocations/{invocation_id}/start",
    response_model=AutomationInvocationRead,
    dependencies=[Depends(require_internal_token)],
)
async def internal_start_automation_invocation(
    invocation_id: uuid.UUID,
    body: InternalAutomationStart,
    session: AsyncSession = Depends(get_session),
) -> AutomationInvocation:
    invocation, automation, task = await _internal_invocation(invocation_id, session, lock=True)
    if invocation.status == "completed":
        return invocation
    if invocation.status == "failed":
        raise HTTPException(status_code=409, detail="Failed automation invocation cannot be started")
    if not automation.enabled:
        raise HTTPException(status_code=409, detail="Automation authorization is no longer active")
    execution = await session.get(WorkflowExecution, body.workflow_execution_id)
    if execution is None or execution.task_id != task.id:
        raise HTTPException(status_code=409, detail="Workflow execution does not belong to automation Task")
    invocation.workflow_execution_id = execution.id
    invocation.status = "running"
    invocation.started_at = invocation.started_at or datetime.now(UTC)
    await session.commit()
    await session.refresh(invocation)
    return invocation


@router.post(
    "/internal/v1/automation-invocations/{invocation_id}/complete",
    response_model=AutomationInvocationRead,
    dependencies=[Depends(require_internal_token)],
)
async def internal_complete_automation_invocation(
    invocation_id: uuid.UUID,
    body: InternalAutomationComplete,
    session: AsyncSession = Depends(get_session),
) -> AutomationInvocation:
    invocation, _automation, _task = await _internal_invocation(invocation_id, session, lock=True)
    if invocation.status == "completed":
        if invocation.response_status != body.response_status or invocation.result_json != body.result:
            raise HTTPException(status_code=409, detail="Completed automation result cannot be rebound")
        return invocation
    if invocation.status == "failed":
        raise HTTPException(status_code=409, detail="Failed automation invocation cannot be completed")

    invocation.status = "completed"
    invocation.response_status = body.response_status
    invocation.result_json = body.result
    invocation.outcome_ambiguous = False
    invocation.last_error = None
    invocation.completed_at = datetime.now(UTC)
    await enqueue_domain_event(
        session,
        event_type="automation.invocation.completed",
        aggregate_type="automation_invocation",
        aggregate_id=invocation.id,
        correlation_id=invocation.correlation_id,
        payload={
            "automation_invocation_id": str(invocation.id),
            "automation_id": str(invocation.automation_id),
            "task_id": str(invocation.task_id),
            "response_status": body.response_status,
        },
    )
    await append_audit(
        session,
        actor_type="worker",
        actor_id=str(invocation.workflow_execution_id) if invocation.workflow_execution_id else None,
        action="automation.invoke.complete",
        resource_type="automation_invocation",
        resource_id=str(invocation.id),
        authority_level=1,
        correlation_id=invocation.correlation_id,
        idempotency_key=f"automation-invocation:{invocation.id}:complete",
        result_json={"response_status": body.response_status, **body.result},
    )
    await session.commit()
    await session.refresh(invocation)
    return invocation


@router.post(
    "/internal/v1/automation-invocations/{invocation_id}/fail",
    response_model=AutomationInvocationRead,
    dependencies=[Depends(require_internal_token)],
)
async def internal_fail_automation_invocation(
    invocation_id: uuid.UUID,
    body: InternalAutomationFail,
    session: AsyncSession = Depends(get_session),
) -> AutomationInvocation:
    invocation, _automation, _task = await _internal_invocation(invocation_id, session, lock=True)
    if invocation.status == "completed":
        return invocation

    transitioned = invocation.status != "failed"
    invocation.status = "failed"
    invocation.response_status = body.response_status
    invocation.result_json = body.result
    invocation.outcome_ambiguous = body.outcome_ambiguous
    invocation.last_error = body.error
    invocation.completed_at = invocation.completed_at or datetime.now(UTC)
    if transitioned:
        await enqueue_domain_event(
            session,
            event_type="automation.invocation.failed",
            aggregate_type="automation_invocation",
            aggregate_id=invocation.id,
            correlation_id=invocation.correlation_id,
            payload={
                "automation_invocation_id": str(invocation.id),
                "automation_id": str(invocation.automation_id),
                "task_id": str(invocation.task_id),
                "response_status": body.response_status,
                "outcome_ambiguous": body.outcome_ambiguous,
            },
        )
        await append_audit(
            session,
            actor_type="worker",
            actor_id=str(invocation.workflow_execution_id) if invocation.workflow_execution_id else None,
            action="automation.invoke.fail",
            resource_type="automation_invocation",
            resource_id=str(invocation.id),
            authority_level=1,
            correlation_id=invocation.correlation_id,
            idempotency_key=f"automation-invocation:{invocation.id}:fail",
            result_json={
                "response_status": body.response_status,
                "outcome_ambiguous": body.outcome_ambiguous,
                "error": body.error[:4000],
                **body.result,
            },
        )
    await session.commit()
    await session.refresh(invocation)
    return invocation
