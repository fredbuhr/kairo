from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .command_models import Conversation, ConversationMessage
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .memory import MEMORY_SOURCE_TYPE, _ensure_memory_project
from .memory_models import MemoryProjectionRecord
from .models import Project, Task, WorkflowExecution
from .security import require_internal_token
from .workflows import run_task

router = APIRouter(prefix="/v1/account/derived-memory", tags=["account-lifecycle"])
internal_router = APIRouter(prefix="/internal/v1/account/derived-memory", tags=["account-lifecycle-internal"])

_TERMINAL_TASK_STATUSES = {"completed", "done", "failed", "cancelled", "archived"}


class DerivedMemoryPurgeRunRead(BaseModel):
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None = None
    workflow_status: str | None = None
    cutoff_message_created_at: datetime | None = None
    already_running: bool = False


class InternalDerivedMemoryPurgeContext(BaseModel):
    task_id: uuid.UUID
    owner_subject: str
    mem0_user_id: str
    graphiti_group_ids: list[str]
    cutoff_message_created_at: datetime | None
    canonical_message_count: int
    requires_real_projectors: bool


class InternalDerivedMemoryPurgeReport(BaseModel):
    projector_mode: Literal["real", "stub"]
    mem0_purged: bool
    graphiti_purged: bool
    graphiti_group_count: int = Field(ge=0)
    verified: bool


class InternalDerivedMemoryPurgeReportRead(BaseModel):
    task_id: uuid.UUID
    projection_rows_removed: int
    projector_mode: str
    verified: bool


async def _latest_owned_message_at(session: AsyncSession, subject: str) -> datetime | None:
    return await session.scalar(
        select(func.max(ConversationMessage.created_at))
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.subject_ref == subject)
    )


async def _owned_message_ids(subject: str):
    return (
        select(ConversationMessage.id)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.subject_ref == subject)
    )


async def _requires_real_projectors(session: AsyncSession, subject: str) -> bool:
    message_ids = await _owned_message_ids(subject)
    metadata_rows = await session.execute(
        select(MemoryProjectionRecord.metadata_json).where(
            MemoryProjectionRecord.source_type == MEMORY_SOURCE_TYPE,
            MemoryProjectionRecord.source_id.in_(message_ids),
        )
    )
    for metadata in metadata_rows.scalars():
        backend = str((metadata or {}).get("backend") or "").strip()
        if backend and backend != "deterministic-stub":
            return True
    return False


async def _memory_purge_task(
    session: AsyncSession,
    task_id: uuid.UUID,
    *,
    lock: bool = False,
) -> tuple[Task, Project]:
    statement = (
        select(Task, Project)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id)
    )
    if lock:
        statement = statement.with_for_update()
    row = (await session.execute(statement)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Derived-memory purge Task not found")
    task, project = row
    task_input = task.input if isinstance(task.input, dict) else {}
    if str(task_input.get("capability") or "") != "memory.purge":
        raise HTTPException(status_code=409, detail="Task is not a derived-memory purge")
    return task, project


@router.post("/purge", response_model=DerivedMemoryPurgeRunRead, status_code=status.HTTP_202_ACCEPTED)
async def request_derived_memory_purge(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> DerivedMemoryPurgeRunRead:
    project = await _ensure_memory_project(session, principal.subject)

    active = await session.scalar(
        select(Task)
        .where(
            Task.project_id == project.id,
            Task.input["capability"].astext == "memory.purge",
            ~Task.status.in_(_TERMINAL_TASK_STATUSES),
        )
        .order_by(Task.created_at.desc())
        .limit(1)
    )
    if active is not None:
        run = await run_task(active.id, session)
        cutoff_raw = (active.input or {}).get("purge_cutoff_at")
        cutoff = datetime.fromisoformat(str(cutoff_raw)) if cutoff_raw else None
        return DerivedMemoryPurgeRunRead(
            task_id=active.id,
            workflow_execution_id=run.workflow_execution_id,
            workflow_status=run.status,
            cutoff_message_created_at=cutoff,
            already_running=True,
        )

    cutoff = await _latest_owned_message_at(session, principal.subject)
    conversation_count = int(
        await session.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.subject_ref == principal.subject)
        )
        or 0
    )
    message_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
            .where(Conversation.subject_ref == principal.subject)
        )
        or 0
    )

    task = Task(
        project_id=project.id,
        title="Purger la mémoire dérivée KAIRO",
        description=(
            "Supprime les projections reconstruisibles Mem0 et Graphiti pour les conversations "
            "canoniques du compte, sans supprimer les conversations elles-mêmes."
        ),
        status="todo",
        owner_type="system",
        owner_ref="account-memory-purge",
        authority_ceiling=1,
        budget_usd=Decimal("0"),
        input={
            "capability": "memory.purge",
            "authority_level": 1,
            "estimated_cost_usd": "0",
            "purge_cutoff_at": cutoff.isoformat() if cutoff else None,
            "canonical_conversation_count": conversation_count,
            "canonical_message_count": message_count,
            "policy_scope": {
                "operation": "purge_rebuildable_memory",
                "canonical_conversations_preserved": True,
            },
        },
    )
    session.add(task)
    await session.flush()

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="account.derived_memory.purge.requested",
        aggregate_type="task",
        aggregate_id=task.id,
        correlation_id=correlation_id,
        payload={
            "task_id": str(task.id),
            "cutoff_message_created_at": cutoff.isoformat() if cutoff else None,
            "canonical_message_count": message_count,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="account.derived_memory.purge.request",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "canonical_conversation_count": conversation_count,
            "canonical_message_count": message_count,
            "cutoff_message_created_at": cutoff.isoformat() if cutoff else None,
        },
    )
    await session.commit()

    run = await run_task(task.id, session)
    return DerivedMemoryPurgeRunRead(
        task_id=task.id,
        workflow_execution_id=run.workflow_execution_id,
        workflow_status=run.status,
        cutoff_message_created_at=cutoff,
    )


@internal_router.get(
    "/purges/{task_id}/context",
    response_model=InternalDerivedMemoryPurgeContext,
    dependencies=[Depends(require_internal_token)],
)
async def internal_derived_memory_purge_context(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> InternalDerivedMemoryPurgeContext:
    task, project = await _memory_purge_task(session, task_id)
    if task.status in {"completed", "done"}:
        raise HTTPException(status_code=409, detail="Derived-memory purge is already completed")

    conversations = list(
        (
            await session.execute(
                select(Conversation.id)
                .where(Conversation.subject_ref == project.keycloak_subject)
                .order_by(Conversation.id)
            )
        ).scalars()
    )
    message_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
            .where(Conversation.subject_ref == project.keycloak_subject)
        )
        or 0
    )
    cutoff_raw = (task.input or {}).get("purge_cutoff_at")
    cutoff = datetime.fromisoformat(str(cutoff_raw)) if cutoff_raw else None
    return InternalDerivedMemoryPurgeContext(
        task_id=task.id,
        owner_subject=project.keycloak_subject,
        mem0_user_id=f"subject:{project.keycloak_subject}",
        graphiti_group_ids=[f"conversation:{conversation_id}" for conversation_id in conversations],
        cutoff_message_created_at=cutoff,
        canonical_message_count=message_count,
        requires_real_projectors=await _requires_real_projectors(
            session,
            project.keycloak_subject,
        ),
    )


@internal_router.post(
    "/purges/{task_id}/report",
    response_model=InternalDerivedMemoryPurgeReportRead,
    dependencies=[Depends(require_internal_token)],
)
async def internal_report_derived_memory_purge(
    task_id: uuid.UUID,
    body: InternalDerivedMemoryPurgeReport,
    session: AsyncSession = Depends(get_session),
) -> InternalDerivedMemoryPurgeReportRead:
    task, project = await _memory_purge_task(session, task_id, lock=True)
    if not body.verified or not body.mem0_purged or not body.graphiti_purged:
        raise HTTPException(status_code=409, detail="Derived-memory purge was not fully verified")
    if body.projector_mode == "stub" and await _requires_real_projectors(
        session,
        project.keycloak_subject,
    ):
        raise HTTPException(
            status_code=409,
            detail="Real derived memory exists; stub mode cannot clear the canonical purge ledger",
        )

    execution = await session.scalar(
        select(WorkflowExecution).where(WorkflowExecution.task_id == task.id)
    )
    if execution is None:
        raise HTTPException(status_code=409, detail="Derived-memory purge WorkflowExecution is missing")

    owned_message_ids = await _owned_message_ids(project.keycloak_subject)
    result = await session.execute(
        delete(MemoryProjectionRecord).where(
            MemoryProjectionRecord.source_type == MEMORY_SOURCE_TYPE,
            MemoryProjectionRecord.source_id.in_(owned_message_ids),
        )
    )
    removed = int(result.rowcount or 0)

    if removed:
        await enqueue_domain_event(
            session,
            event_type="account.derived_memory.purge.projector_ledger_cleared",
            aggregate_type="task",
            aggregate_id=task.id,
            correlation_id=execution.correlation_id,
            payload={
                "task_id": str(task.id),
                "projection_rows_removed": removed,
                "projector_mode": body.projector_mode,
            },
        )
        await append_audit(
            session,
            actor_type="worker",
            actor_id=execution.workflow_id,
            action="account.derived_memory.purge.ledger_clear",
            resource_type="task",
            resource_id=str(task.id),
            authority_level=1,
            correlation_id=execution.correlation_id,
            result_json={
                "projection_rows_removed": removed,
                "projector_mode": body.projector_mode,
                "graphiti_group_count": body.graphiti_group_count,
            },
        )

    await session.commit()
    return InternalDerivedMemoryPurgeReportRead(
        task_id=task.id,
        projection_rows_removed=removed,
        projector_mode=body.projector_mode,
        verified=True,
    )
