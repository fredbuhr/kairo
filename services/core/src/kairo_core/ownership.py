from __future__ import annotations

import uuid
from typing import Iterable, Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .autonomy_models import ApprovalRequest
from .command_models import Conversation
from .document_models import Document
from .models import Artifact, Asset, Project, Task, WorkflowExecution

DEVELOPMENT_SUBJECT = "development-user"
OWNER_SYSTEM_PROJECT_KEYS = frozenset({"assistant", "news", "documents", "memory"})


def _derived_system_project_id(subject: str, key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:project:{key}:subject:{subject}")


def owner_system_project_ids(
    subject: str,
    keys: Iterable[str] = OWNER_SYSTEM_PROJECT_KEYS,
) -> frozenset[uuid.UUID]:
    """Return the per-user system Project IDs that are product internals, not user Projects.

    Authenticated production subjects always use these derived IDs. Historical auth-disabled
    development IDs remain migration compatibility details and are intentionally not inferred here:
    product read models use this helper to keep KAIRO's own plumbing out of normal Project/Home views
    without relying on editable display names.
    """

    return frozenset(_derived_system_project_id(subject, key) for key in keys)


def is_owner_system_project(project_id: uuid.UUID, subject: str) -> bool:
    return project_id in owner_system_project_ids(subject)


def scoped_system_project_id(
    subject: str,
    key: str,
    *,
    legacy_development_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Return the preferred stable per-subject system Project identity.

    Auth-disabled development may reuse a historical ID only when that row is not already reserved
    as a system-owned migration workspace. `ensure_system_project` detects that collision and falls
    back to the derived per-subject UUID, so authenticated and legacy/system rows never alias.
    """

    if subject == DEVELOPMENT_SUBJECT and legacy_development_id is not None:
        return legacy_development_id
    return _derived_system_project_id(subject, key)


async def ensure_system_project(
    session: AsyncSession,
    *,
    subject: str,
    key: str,
    name: str,
    summary: str,
    legacy_development_id: uuid.UUID | None = None,
) -> tuple[Project, bool]:
    if key not in OWNER_SYSTEM_PROJECT_KEYS:
        raise ValueError(f"Unknown owner-scoped KAIRO system project key: {key}")

    project_id = scoped_system_project_id(
        subject,
        key,
        legacy_development_id=legacy_development_id,
    )
    existing = await session.get(Project, project_id)
    if existing is not None and existing.keycloak_subject != subject:
        # Migrations deliberately preserve certain historical workspace IDs as __kairo_system__.
        # Never seize such a row for a user just because auth-disabled development once used it.
        project_id = _derived_system_project_id(subject, key)

    inserted_id = await session.scalar(
        pg_insert(Project)
        .values(
            id=project_id,
            keycloak_subject=subject,
            name=name,
            status="active",
            summary=summary,
            parent_id=None,
        )
        .on_conflict_do_nothing(index_elements=[Project.id])
        .returning(Project.id)
    )
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.keycloak_subject == subject,
        )
    )
    if project is None:
        raise RuntimeError(f"KAIRO system project {key} could not be initialized for subject")
    return project, inserted_id is not None


async def owned_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    subject: str,
    *,
    lock: bool = False,
) -> Project | None:
    statement = select(Project).where(
        Project.id == project_id,
        Project.keycloak_subject == subject,
    )
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def require_owned_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    subject: str,
    *,
    lock: bool = False,
) -> Project:
    project = await owned_project(session, project_id, subject, lock=lock)
    if project is None:
        # Deliberately collapse foreign ownership and absence into one 404 response.
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def owned_task(
    session: AsyncSession,
    task_id: uuid.UUID,
    subject: str,
    *,
    lock: bool = False,
) -> Task | None:
    statement = (
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.keycloak_subject == subject)
    )
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def entity_belongs_to_subject(
    session: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    subject: str,
) -> bool:
    normalized = entity_type.strip().lower().replace("-", "_")
    aliases = {
        "workflow": "workflow_execution",
        "execution": "workflow_execution",
        "approval_request": "approval",
    }
    normalized = aliases.get(normalized, normalized)

    if normalized == "project":
        return await owned_project(session, entity_id, subject) is not None
    if normalized == "task":
        return await owned_task(session, entity_id, subject) is not None
    if normalized == "conversation":
        return (
            await session.scalar(
                select(Conversation.id).where(
                    Conversation.id == entity_id,
                    Conversation.subject_ref == subject,
                )
            )
            is not None
        )
    if normalized == "document":
        return (
            await session.scalar(
                select(Document.id).where(
                    Document.id == entity_id,
                    Document.keycloak_subject == subject,
                )
            )
            is not None
        )
    if normalized == "asset":
        return (
            await session.scalar(
                select(Asset.id).where(
                    Asset.id == entity_id,
                    Asset.keycloak_subject == subject,
                )
            )
            is not None
        )
    if normalized == "artifact":
        return (
            await session.scalar(
                select(Artifact.id)
                .join(Project, Project.id == Artifact.project_id)
                .where(Artifact.id == entity_id, Project.keycloak_subject == subject)
            )
            is not None
        )
    if normalized == "workflow_execution":
        return (
            await session.scalar(
                select(WorkflowExecution.id)
                .join(Task, Task.id == WorkflowExecution.task_id)
                .join(Project, Project.id == Task.project_id)
                .where(
                    WorkflowExecution.id == entity_id,
                    Project.keycloak_subject == subject,
                )
            )
            is not None
        )
    if normalized == "approval":
        return (
            await session.scalar(
                select(ApprovalRequest.id)
                .join(Task, Task.id == ApprovalRequest.task_id)
                .join(Project, Project.id == Task.project_id)
                .where(
                    ApprovalRequest.id == entity_id,
                    Project.keycloak_subject == subject,
                )
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
    subject: str,
) -> None:
    source_owned = await entity_belongs_to_subject(session, source_type, source_id, subject)
    target_owned = await entity_belongs_to_subject(session, target_type, target_id, subject)
    if not source_owned or not target_owned:
        raise HTTPException(status_code=404, detail="Relationship endpoint not found")


EntityOwnership = Literal[
    "project",
    "task",
    "conversation",
    "document",
    "asset",
    "artifact",
    "workflow_execution",
    "approval",
]
