from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .autonomy_models import ApprovalRequest, ModelUsageRecord
from .config import settings
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Project, Task, WorkflowExecution
from .model_admission import (
    expire_reservations, lock_admission, reserve_model_call, settle_reservation, task_exposure,
)
from .project_access import get_owned_task, owned_project_clause
from .security import require_internal_token

router = APIRouter()

POLICY_TOKEN_TTL = timedelta(minutes=5)
DEFAULT_APPROVAL_TTL = timedelta(hours=24)


class ApprovalCreate(BaseModel):
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None = None
    action: str = Field(min_length=1, max_length=160)
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str | None = Field(default=None, max_length=320)
    authority_level: int = Field(ge=1, le=10)
    reason: str = Field(min_length=1, max_length=4000)
    scope: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None
    requested_by: str
    action: str
    resource_type: str
    resource_id: str | None
    authority_level: int
    reason: str
    scope_json: dict[str, Any]
    status: str
    decided_by: str | None
    decision_note: str | None
    expires_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "denied"]
    note: str | None = Field(default=None, max_length=4000)


class PolicyAuthorizeRequest(BaseModel):
    task_id: uuid.UUID
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=160)
    workflow_execution_id: uuid.UUID | None = None
    action: str = Field(min_length=1, max_length=160)
    resource_type: str = Field(default="tool", min_length=1, max_length=80)
    resource_id: str | None = Field(default=None, max_length=320)
    authority_level: int = Field(ge=1, le=10)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    scope: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="Autonomous activity requires policy authorization", max_length=4000)


class PolicyAuthorizeResponse(BaseModel):
    allowed: bool
    reason: str
    approval_required: bool = False
    approval_request_id: uuid.UUID | None = None
    policy_token: str | None = None
    spent_usd: Decimal = Decimal("0")
    budget_usd: Decimal | None = None
    remaining_usd: Decimal | None = None


class PolicyValidateRequest(BaseModel):
    policy_token: str
    task_id: uuid.UUID | None = None
    action: str | None = None


class PolicyValidateResponse(BaseModel):
    valid: bool
    claims: dict[str, Any] = Field(default_factory=dict)


class ModelUsageCreate(BaseModel):
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None = None
    correlation_id: uuid.UUID
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=160)
    provider: str = Field(min_length=1, max_length=80)
    model_alias: str = Field(min_length=1, max_length=120)
    model_name: str | None = Field(default=None, max_length=240)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BudgetRead(BaseModel):
    task_id: uuid.UUID
    budget_usd: Decimal | None
    spent_usd: Decimal
    remaining_usd: Decimal | None
    exhausted: bool
    reserved_usd: Decimal = Decimal("0")
    uncertain_usd: Decimal = Decimal("0")
    uncertain_calls: int = 0
    over_budget: bool = False


def _remaining(task: Task, spent: Decimal) -> Decimal | None:
    if task.budget_usd is None:
        return None
    return max(Decimal("0"), Decimal(task.budget_usd) - spent)


async def _budget_read(session: AsyncSession, task: Task) -> BudgetRead:
    exposure = await task_exposure(session, task.id)
    spent = exposure["spent"]
    budget = Decimal(task.budget_usd) if task.budget_usd is not None else None
    committed = spent + exposure["reserved"] + exposure["uncertain"]
    remaining = _remaining(task, committed)
    return BudgetRead(
        task_id=task.id,
        budget_usd=budget,
        spent_usd=spent,
        remaining_usd=remaining,
        exhausted=budget is not None and committed >= budget,
        reserved_usd=exposure["reserved"],
        uncertain_usd=exposure["uncertain"],
        uncertain_calls=exposure["uncertain_calls"],
        over_budget=budget is not None and committed > budget,
    )


def _mint_policy_token(
    *,
    task: Task,
    action: str,
    authority_level: int,
    scope: dict[str, Any],
    approval_request_id: uuid.UUID | None,
    workflow_execution_id: uuid.UUID | None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "iss": "kairo-core",
        "sub": "kairo-policy",
        "iat": int(now.timestamp()),
        "exp": int((now + POLICY_TOKEN_TTL).timestamp()),
        "jti": str(uuid.uuid4()),
        "task_id": str(task.id),
        "workflow_execution_id": str(workflow_execution_id) if workflow_execution_id else None,
        "action": action,
        "authority_level": authority_level,
        "scope": scope,
        "approval_request_id": str(approval_request_id) if approval_request_id else None,
    }
    return jwt.encode(payload, settings.kairo_policy_signing_key, algorithm="HS256")


@router.post(
    "/v1/approval-requests",
    response_model=ApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_approval_request(
    body: ApprovalCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> ApprovalRequest:
    task = await get_owned_task(session, body.task_id, principal)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.authority_level > task.authority_ceiling:
        raise HTTPException(status_code=409, detail="Requested authority exceeds task authority ceiling")
    if body.workflow_execution_id:
        execution = await session.get(WorkflowExecution, body.workflow_execution_id)
        if not execution or execution.task_id != task.id:
            raise HTTPException(status_code=404, detail="Workflow execution not found")

    correlation_id = uuid.uuid4()
    approval = ApprovalRequest(
        task_id=body.task_id,
        workflow_execution_id=body.workflow_execution_id,
        requested_by=principal.subject,
        action=body.action,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        authority_level=body.authority_level,
        reason=body.reason,
        scope_json=body.scope,
        expires_at=body.expires_at or datetime.now(UTC) + DEFAULT_APPROVAL_TTL,
    )
    session.add(approval)
    await session.flush()
    await enqueue_domain_event(
        session,
        event_type="approval.requested",
        aggregate_type="approval_request",
        aggregate_id=approval.id,
        correlation_id=correlation_id,
        payload={
            "approval_request_id": str(approval.id),
            "task_id": str(task.id),
            "action": approval.action,
            "authority_level": approval.authority_level,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="approval.request",
        resource_type="approval_request",
        resource_id=str(approval.id),
        authority_level=body.authority_level,
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(approval)
    return approval


@router.get("/v1/approval-requests", response_model=list[ApprovalRead])
async def list_approval_requests(
    task_id: uuid.UUID | None = None,
    approval_status: str | None = None,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalRequest]:
    if task_id is not None and await get_owned_task(session, task_id, principal) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    statement = (
        select(ApprovalRequest)
        .join(Task, Task.id == ApprovalRequest.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(owned_project_clause(principal))
        .order_by(ApprovalRequest.created_at.desc())
    )
    if task_id:
        statement = statement.where(ApprovalRequest.task_id == task_id)
    if approval_status:
        statement = statement.where(ApprovalRequest.status == approval_status)
    result = await session.execute(statement)
    return list(result.scalars())


@router.post("/v1/approval-requests/{approval_id}/decision", response_model=ApprovalRead)
async def decide_approval_request(
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> ApprovalRequest:
    approval = await session.scalar(
        select(ApprovalRequest)
        .join(Task, Task.id == ApprovalRequest.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(ApprovalRequest.id == approval_id, owned_project_clause(principal))
        .with_for_update()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval request is no longer pending")
    now = datetime.now(UTC)
    if approval.expires_at and approval.expires_at <= now:
        approval.status = "expired"
        await session.commit()
        raise HTTPException(status_code=409, detail="Approval request has expired")

    approval.status = body.decision
    approval.decided_by = principal.subject
    approval.decision_note = body.note
    approval.decided_at = now
    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type=f"approval.{body.decision}",
        aggregate_type="approval_request",
        aggregate_id=approval.id,
        correlation_id=correlation_id,
        payload={
            "approval_request_id": str(approval.id),
            "task_id": str(approval.task_id),
            "action": approval.action,
            "authority_level": approval.authority_level,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action=f"approval.{body.decision}",
        resource_type="approval_request",
        resource_id=str(approval.id),
        authority_level=approval.authority_level,
        correlation_id=correlation_id,
        result_json={"decision": body.decision, "note": body.note},
    )
    await session.commit()
    await session.refresh(approval)
    return approval


@router.get("/v1/tasks/{task_id}/budget", response_model=BudgetRead)
async def get_task_budget(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> BudgetRead:
    task = await get_owned_task(session, task_id, principal)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await _budget_read(session, task)


@router.post(
    "/internal/v1/policy/authorize",
    response_model=PolicyAuthorizeResponse,
    dependencies=[Depends(require_internal_token)],
)
async def authorize_activity(
    body: PolicyAuthorizeRequest,
    session: AsyncSession = Depends(get_session),
) -> PolicyAuthorizeResponse:
    is_model = body.action == "model.invoke"
    if is_model:
        if not body.idempotency_key or body.resource_type != "model_alias" or body.resource_id not in {"smart", "alternative", "local-fast"}:
            raise HTTPException(422, "Model authorization requires a stable call key and canonical alias")
        await lock_admission(session)
        await expire_reservations(session)
    task = await session.get(Task, body.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.workflow_execution_id:
        execution = await session.get(WorkflowExecution, body.workflow_execution_id)
        if not execution or execution.task_id != task.id:
            raise HTTPException(status_code=404, detail="Workflow execution not found for task")

    exposure = await task_exposure(session, task.id)
    spent = exposure["spent"]
    budget = Decimal(task.budget_usd) if task.budget_usd is not None else None
    committed = spent + exposure["reserved"] + exposure["uncertain"]
    remaining = _remaining(task, committed)
    if body.authority_level > task.authority_ceiling:
        return PolicyAuthorizeResponse(
            allowed=False,
            reason="authority_ceiling_exceeded",
            spent_usd=spent,
            budget_usd=budget,
            remaining_usd=remaining,
        )
    if not is_model and budget is not None and committed + body.estimated_cost_usd > budget:
        return PolicyAuthorizeResponse(
            allowed=False,
            reason="hard_budget_exceeded",
            spent_usd=spent,
            budget_usd=budget,
            remaining_usd=remaining,
        )

    approval: ApprovalRequest | None = None
    if body.authority_level > 1:
        now = datetime.now(UTC)
        approval = await session.scalar(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.task_id == task.id,
                ApprovalRequest.action == body.action,
                ApprovalRequest.resource_type == body.resource_type,
                ApprovalRequest.resource_id == body.resource_id,
                ApprovalRequest.scope_json == body.scope,
                ApprovalRequest.status == "approved",
                ApprovalRequest.authority_level >= body.authority_level,
            )
            .order_by(ApprovalRequest.decided_at.desc())
        )
        if approval and approval.expires_at and approval.expires_at <= now:
            approval = None

        if approval is None:
            pending = await session.scalar(
                select(ApprovalRequest)
                .where(
                    ApprovalRequest.task_id == task.id,
                    ApprovalRequest.action == body.action,
                    ApprovalRequest.resource_type == body.resource_type,
                    ApprovalRequest.resource_id == body.resource_id,
                    ApprovalRequest.scope_json == body.scope,
                    ApprovalRequest.status == "pending",
                    ApprovalRequest.authority_level >= body.authority_level,
                )
                .order_by(ApprovalRequest.created_at.desc())
            )
            if pending is None:
                pending = ApprovalRequest(
                    task_id=task.id,
                    workflow_execution_id=body.workflow_execution_id,
                    requested_by="kairo-worker",
                    action=body.action,
                    resource_type=body.resource_type,
                    resource_id=body.resource_id,
                    authority_level=body.authority_level,
                    reason=body.reason,
                    scope_json=body.scope,
                    expires_at=now + DEFAULT_APPROVAL_TTL,
                )
                session.add(pending)
                await session.flush()
                correlation_id = uuid.uuid4()
                await enqueue_domain_event(
                    session,
                    event_type="approval.requested",
                    aggregate_type="approval_request",
                    aggregate_id=pending.id,
                    correlation_id=correlation_id,
                    payload={
                        "approval_request_id": str(pending.id),
                        "task_id": str(task.id),
                        "action": body.action,
                        "authority_level": body.authority_level,
                    },
                )
                await session.commit()
            return PolicyAuthorizeResponse(
                allowed=False,
                reason="approval_required",
                approval_required=True,
                approval_request_id=pending.id,
                spent_usd=spent,
                budget_usd=budget,
                remaining_usd=remaining,
            )

    if is_model:
        denial = await reserve_model_call(
            session, task=task, key=body.idempotency_key,
            execution_id=body.workflow_execution_id, model_alias=body.resource_id,
            amount=body.estimated_cost_usd,
        )
        await session.commit()
        if denial:
            return PolicyAuthorizeResponse(allowed=False, reason=denial, spent_usd=spent,
                                           budget_usd=budget, remaining_usd=remaining)
    token = _mint_policy_token(
        task=task,
        action=body.action,
        authority_level=body.authority_level,
        scope=body.scope,
        approval_request_id=approval.id if approval else None,
        workflow_execution_id=body.workflow_execution_id,
    )
    return PolicyAuthorizeResponse(
        allowed=True,
        reason="approved" if approval else "within_default_authority",
        approval_request_id=approval.id if approval else None,
        policy_token=token,
        spent_usd=spent,
        budget_usd=budget,
        remaining_usd=remaining,
    )


@router.post(
    "/internal/v1/policy/validate",
    response_model=PolicyValidateResponse,
    dependencies=[Depends(require_internal_token)],
)
async def validate_policy_token(body: PolicyValidateRequest) -> PolicyValidateResponse:
    try:
        claims = jwt.decode(
            body.policy_token,
            settings.kairo_policy_signing_key,
            algorithms=["HS256"],
            issuer="kairo-core",
            options={"require": ["exp", "iat", "jti", "sub", "task_id", "action"]},
        )
        if claims.get("sub") != "kairo-policy":
            raise jwt.InvalidTokenError("Unexpected policy token subject")
        if body.task_id and claims.get("task_id") != str(body.task_id):
            raise jwt.InvalidTokenError("Policy token task mismatch")
        if body.action and claims.get("action") != body.action:
            raise jwt.InvalidTokenError("Policy token action mismatch")
        return PolicyValidateResponse(valid=True, claims=dict(claims))
    except jwt.PyJWTError:
        return PolicyValidateResponse(valid=False, claims={})


@router.post(
    "/internal/v1/model-usage",
    response_model=BudgetRead,
    dependencies=[Depends(require_internal_token)],
)
async def record_model_usage(
    body: ModelUsageCreate,
    session: AsyncSession = Depends(get_session),
) -> BudgetRead:
    # Locking the task serializes ledger writes for one durable task. Combined with the unique
    # idempotency key, a Worker can safely retry a request after an ambiguous HTTP response.
    await lock_admission(session)
    task = await session.get(Task, body.task_id, with_for_update=True)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.workflow_execution_id:
        execution = await session.get(WorkflowExecution, body.workflow_execution_id)
        if not execution or execution.task_id != task.id:
            raise HTTPException(status_code=404, detail="Workflow execution not found for task")

    if body.idempotency_key:
        existing = await session.scalar(
            select(ModelUsageRecord).where(
                ModelUsageRecord.idempotency_key == body.idempotency_key
            )
        )
        if existing:
            if (existing.task_id != task.id or existing.model_alias != body.model_alias
                    or existing.workflow_execution_id != body.workflow_execution_id):
                raise HTTPException(
                    status_code=409,
                    detail="Model usage idempotency key is already bound to another invocation",
                )
            if existing.provider != body.provider:
                raise HTTPException(409, "Model usage provider differs from canonical accounting")
            if existing.metadata_json.get("cost_reported") is False and body.metadata.get("cost_reported") is True:
                await settle_reservation(
                    session, key=body.idempotency_key, task=task,
                    execution_id=body.workflow_execution_id, model_alias=body.model_alias,
                    cost=body.cost_usd, cost_reported=True,
                )
                previous = existing.cost_usd
                existing.cost_usd = body.cost_usd
                existing.metadata_json = {**existing.metadata_json, **body.metadata}
                await append_audit(
                    session, actor_type="worker", actor_id=body.model_alias,
                    action="model.usage.reconcile", resource_type="task", resource_id=str(task.id),
                    authority_level=1, correlation_id=body.correlation_id,
                    result_json={"idempotency_key": body.idempotency_key,
                                 "previous_cost_usd": str(previous), "cost_usd": str(body.cost_usd)},
                )
                await session.commit()
                return await _budget_read(session, task)
            if existing.cost_usd != body.cost_usd or existing.provider != body.provider:
                raise HTTPException(409, "Model usage replay differs from canonical accounting")
            return await _budget_read(session, task)

    settlement = await settle_reservation(
        session, key=body.idempotency_key, task=task, execution_id=body.workflow_execution_id,
        model_alias=body.model_alias, cost=body.cost_usd,
        cost_reported=body.metadata.get("cost_reported", True) is True,
    )

    total_tokens = body.total_tokens or body.prompt_tokens + body.completion_tokens
    record = ModelUsageRecord(
        task_id=body.task_id,
        workflow_execution_id=body.workflow_execution_id,
        correlation_id=body.correlation_id,
        idempotency_key=body.idempotency_key,
        provider=body.provider,
        model_alias=body.model_alias,
        model_name=body.model_name,
        prompt_tokens=body.prompt_tokens,
        completion_tokens=body.completion_tokens,
        total_tokens=total_tokens,
        cost_usd=body.cost_usd,
        metadata_json={**body.metadata, **settlement},
    )
    session.add(record)
    await session.flush()
    await append_audit(
        session,
        actor_type="worker",
        actor_id=body.model_alias,
        action="model.usage.record",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=1,
        correlation_id=body.correlation_id,
        result_json={
            "provider": body.provider,
            "model_alias": body.model_alias,
            "idempotency_key": body.idempotency_key,
            "total_tokens": total_tokens,
            "cost_usd": str(body.cost_usd),
            **settlement,
        },
    )
    await session.commit()
    return await _budget_read(session, task)
