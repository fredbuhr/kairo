from __future__ import annotations

import uuid

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from .auth import Principal
from .config import settings
from .models import Project


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
