from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Project
from .schemas import ProjectRead


router = APIRouter(tags=["projects"])


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    summary: str | None = None
    parent_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_name(self) -> "ProjectUpdate":
        if "name" in self.model_fields_set and self.name is not None and not self.name.strip():
            raise ValueError("name cannot be blank")
        return self


async def _validate_parent(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    parent_id: uuid.UUID | None,
) -> None:
    if parent_id is None:
        return
    if parent_id == project_id:
        raise HTTPException(status_code=409, detail="A project cannot be its own parent")

    current = await session.get(Project, parent_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Parent project not found")

    # Follow the canonical parent chain. If the project itself appears, the new link would create a
    # cycle and is rejected rather than repaired in the UI.
    visited: set[uuid.UUID] = set()
    while current is not None:
        if current.id == project_id:
            raise HTTPException(status_code=409, detail="Project hierarchy cannot contain a cycle")
        if current.id in visited:
            # Defensive fail-closed behavior if pre-existing corrupt hierarchy data is encountered.
            raise HTTPException(status_code=409, detail="Existing project hierarchy contains a cycle")
        visited.add(current.id)
        if current.parent_id is None:
            break
        current = await session.get(Project, current.parent_id)


@router.patch("/v1/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    fields = body.model_fields_set
    if not fields:
        return project

    if "parent_id" in fields:
        await _validate_parent(session, project_id=project.id, parent_id=body.parent_id)

    before: dict[str, Any] = {
        "name": project.name,
        "status": project.status,
        "summary": project.summary,
        "parent_id": str(project.parent_id) if project.parent_id else None,
    }

    if "name" in fields and body.name is not None:
        project.name = body.name.strip()
    if "status" in fields and body.status is not None:
        project.status = body.status.strip()
    if "summary" in fields:
        project.summary = body.summary
    if "parent_id" in fields:
        project.parent_id = body.parent_id

    correlation_id = uuid.uuid4()
    changed = {
        "name": project.name,
        "status": project.status,
        "summary": project.summary,
        "parent_id": str(project.parent_id) if project.parent_id else None,
    }
    await enqueue_domain_event(
        session,
        event_type="project.updated",
        aggregate_type="project",
        aggregate_id=project.id,
        correlation_id=correlation_id,
        payload={
            "project_id": str(project.id),
            "name": project.name,
            "status": project.status,
            "parent_id": str(project.parent_id) if project.parent_id else None,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=None,
        action="project.update",
        resource_type="project",
        resource_id=str(project.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json", exclude_unset=True),
        result_json={"before": before, "after": changed},
    )
    await session.commit()
    await session.refresh(project)
    return project
