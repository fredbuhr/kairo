from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from .auth import Principal
from .autonomy_models import ApprovalRequest
from .command_models import Conversation
from .config import settings
from .document_models import Document
from .models import Artifact, Asset, Project, Task, WorkflowExecution


def owned_project_clause(principal: Principal) -> ColumnElement[bool]:
    owned = Project.owner_subject == principal.subject
    if not settings.kairo_auth_enabled:
        return or_(owned, Project.owner_subject.is_(None))
    return owned


async def get_owned_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    principal: Principal,
) -> Project | None:
    project = await session.get(Project, project_id)
    if project is None:
        return None
    if project.owner_subject == principal.subject:
        return project
    if not settings.kairo_auth_enabled and project.owner_subject is None:
        return project
    return None


def owned_tasks_statement(principal: Principal) -> Select:
    return (
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(owned_project_clause(principal))
    )


async def get_owned_task(
    session: AsyncSession,
    task_id: uuid.UUID,
    principal: Principal,
) -> Task | None:
    task = await session.get(Task, task_id)
    if task is None:
        return None
    if not await get_owned_project(session, task.project_id, principal):
        return None
    return task


async def entity_belongs_to_principal(
    session: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    principal: Principal,
) -> bool:
    """Resolve ownership for polymorphic Relationship endpoints.

    Unknown entity types fail closed. Foreign and missing entities deliberately share the same
    response surface so a caller cannot use Relationship creation as an ownership oracle.
    """

    normalized = entity_type.strip().lower().replace("-", "_")
    normalized = {
        "workflow": "workflow_execution",
        "execution": "workflow_execution",
        "approval_request": "approval",
    }.get(normalized, normalized)

    if normalized == "project":
        return await get_owned_project(session, entity_id, principal) is not None
    if normalized == "task":
        return await get_owned_task(session, entity_id, principal) is not None
    if normalized == "conversation":
        return (
            await session.scalar(
                select(Conversation.id).where(
                    Conversation.id == entity_id,
                    Conversation.subject_ref == principal.subject,
                )
            )
            is not None
        )
    if normalized == "document":
        return (
            await session.scalar(
                select(Document.id).where(
                    Document.id == entity_id,
                    Document.metadata_json["owner_subject"].astext == principal.subject,
                )
            )
            is not None
        )
    if normalized == "asset":
        return (
            await session.scalar(
                select(Asset.id).where(
                    Asset.id == entity_id,
                    Asset.metadata_json["owner_subject"].astext == principal.subject,
                )
            )
            is not None
        )
    if normalized == "artifact":
        return (
            await session.scalar(
                select(Artifact.id)
                .join(Project, Project.id == Artifact.project_id)
                .where(Artifact.id == entity_id, owned_project_clause(principal))
            )
            is not None
        )
    if normalized == "workflow_execution":
        return (
            await session.scalar(
                select(WorkflowExecution.id)
                .join(Task, Task.id == WorkflowExecution.task_id)
                .join(Project, Project.id == Task.project_id)
                .where(WorkflowExecution.id == entity_id, owned_project_clause(principal))
            )
            is not None
        )
    if normalized == "approval":
        return (
            await session.scalar(
                select(ApprovalRequest.id)
                .join(Task, Task.id == ApprovalRequest.task_id)
                .join(Project, Project.id == Task.project_id)
                .where(ApprovalRequest.id == entity_id, owned_project_clause(principal))
            )
            is not None
        )
    return False


async def require_same_owner_entities(
    session: AsyncSession,
    *,
    source_type: str,
    source_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    principal: Principal,
) -> None:
    source_owned = await entity_belongs_to_principal(
        session, source_type, source_id, principal
    )
    target_owned = await entity_belongs_to_principal(
        session, target_type, target_id, principal
    )
    if not source_owned or not target_owned:
        raise HTTPException(status_code=404, detail="Relationship endpoint not found")
