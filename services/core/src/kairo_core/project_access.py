from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from .auth import Principal
from .config import settings
from .models import Project, Task


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
