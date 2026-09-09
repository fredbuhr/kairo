from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .autonomy_models import ApprovalRequest, ModelUsageRecord
from .db import get_session
from .models import Project, Task, WorkflowExecution


router = APIRouter(prefix="/v1/operations", tags=["operations"])


class AgentExecutionRead(BaseModel):
    task_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    task_status: str
    capability: str
    authority_ceiling: int
    budget_usd: Decimal | None = None
    spent_usd: Decimal = Decimal("0")
    pending_approvals: int = 0
    workflow_execution_id: uuid.UUID | None = None
    workflow_id: str | None = None
    workflow_status: str | None = None
    workflow_started_at: datetime | None = None
    workflow_completed_at: datetime | None = None
    last_error: str | None = None
    command_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


def _safe_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _safe_metadata(task: Task) -> dict[str, Any]:
    task_input = task.input if isinstance(task.input, dict) else {}
    allowed_keys = (
        "query",
        "mode",
        "tool_key",
        "document_id",
        "document_version_id",
        "generation",
    )
    return {key: task_input[key] for key in allowed_keys if key in task_input}


@router.get("/agents", response_model=list[AgentExecutionRead])
async def list_agent_executions(
    execution_status: str | None = None,
    limit: int = Query(default=80, ge=10, le=250),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[AgentExecutionRead]:
    statement = (
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Project.keycloak_subject == principal.subject)
        .where(Task.input.has_key("capability"))  # type: ignore[attr-defined]  # PostgreSQL JSONB ? operator
        .order_by(Task.updated_at.desc())
        .limit(limit)
    )
    task_rows = await session.execute(statement)
    tasks = list(task_rows.scalars())
    if not tasks:
        return []

    task_ids = [task.id for task in tasks]
    workflow_rows = await session.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.task_id.in_(task_ids))
        .order_by(WorkflowExecution.updated_at.desc())
    )
    workflow_by_task: dict[uuid.UUID, WorkflowExecution] = {}
    for workflow in workflow_rows.scalars():
        workflow_by_task.setdefault(workflow.task_id, workflow)

    approval_rows = await session.execute(
        select(ApprovalRequest.task_id, func.count(ApprovalRequest.id))
        .where(ApprovalRequest.task_id.in_(task_ids), ApprovalRequest.status == "pending")
        .group_by(ApprovalRequest.task_id)
    )
    pending_by_task = {task_id: int(count or 0) for task_id, count in approval_rows}

    usage_rows = await session.execute(
        select(ModelUsageRecord.task_id, func.coalesce(func.sum(ModelUsageRecord.cost_usd), 0))
        .where(ModelUsageRecord.task_id.in_(task_ids))
        .group_by(ModelUsageRecord.task_id)
    )
    spend_by_task = {task_id: Decimal(str(value or 0)) for task_id, value in usage_rows}

    results: list[AgentExecutionRead] = []
    for task in tasks:
        workflow = workflow_by_task.get(task.id)
        effective_status = workflow.status if workflow is not None else task.status
        if execution_status and effective_status != execution_status:
            continue
        task_input = task.input if isinstance(task.input, dict) else {}
        capability = str(task_input.get("capability") or "unknown")
        results.append(
            AgentExecutionRead(
                task_id=task.id,
                project_id=task.project_id,
                title=task.title,
                task_status=task.status,
                capability=capability,
                authority_ceiling=task.authority_ceiling,
                budget_usd=Decimal(task.budget_usd) if task.budget_usd is not None else None,
                spent_usd=spend_by_task.get(task.id, Decimal("0")),
                pending_approvals=pending_by_task.get(task.id, 0),
                workflow_execution_id=workflow.id if workflow else None,
                workflow_id=workflow.workflow_id if workflow else None,
                workflow_status=workflow.status if workflow else None,
                workflow_started_at=workflow.started_at if workflow else None,
                workflow_completed_at=workflow.completed_at if workflow else None,
                last_error=workflow.last_error if workflow else None,
                command_id=_safe_uuid(task_input.get("command_id")),
                created_at=task.created_at,
                updated_at=task.updated_at,
                metadata=_safe_metadata(task),
            )
        )
    return results
