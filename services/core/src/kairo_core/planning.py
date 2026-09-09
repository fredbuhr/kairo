from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Task


router = APIRouter(tags=["planning"])

_OPEN_EXCLUDED = {"completed", "done", "cancelled", "archived"}
_TERMINAL = {"completed", "done", "cancelled"}
_ACTIVE = {"running", "in_progress"}


class TaskPlanningRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: str
    owner_type: str
    owner_ref: str | None
    authority_ceiling: int
    budget_usd: Decimal | None
    input: dict[str, Any]
    priority: int
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    due_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskPlanningUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=320)
    description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)
    priority: int | None = Field(default=None, ge=0, le=4)
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> "TaskPlanningUpdate":
        if (
            "planned_start_at" in self.model_fields_set
            and "planned_end_at" in self.model_fields_set
            and self.planned_start_at is not None
            and self.planned_end_at is not None
            and self.planned_end_at < self.planned_start_at
        ):
            raise ValueError("planned_end_at must be after planned_start_at")
        return self


class TodayRead(BaseModel):
    generated_at: datetime
    day_start: datetime
    day_end: datetime
    timezone_offset_minutes: int
    overdue: list[TaskPlanningRead]
    due_today: list[TaskPlanningRead]
    planned_today: list[TaskPlanningRead]
    important: list[TaskPlanningRead]


def _day_bounds(offset_minutes: int) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    local_date = (now + timedelta(minutes=offset_minutes)).date()
    local_midnight_as_utc = datetime.combine(local_date, time.min, tzinfo=UTC)
    start = local_midnight_as_utc - timedelta(minutes=offset_minutes)
    return start, start + timedelta(days=1)


def _open_clause():
    return ~Task.status.in_(sorted(_OPEN_EXCLUDED))


@router.get("/v1/planning/tasks", response_model=list[TaskPlanningRead])
async def list_planning_tasks(
    project_id: uuid.UUID | None = None,
    include_closed: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    statement = select(Task).order_by(Task.priority.desc(), Task.updated_at.desc())
    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    if not include_closed:
        statement = statement.where(_open_clause())
    result = await session.execute(statement)
    return list(result.scalars())


@router.patch("/v1/tasks/{task_id}/planning", response_model=TaskPlanningRead)
async def update_task_planning(
    task_id: uuid.UUID,
    body: TaskPlanningUpdate,
    session: AsyncSession = Depends(get_session),
) -> Task:
    task = await session.scalar(select(Task).where(Task.id == task_id).with_for_update())
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    fields = body.model_fields_set
    if not fields:
        return task

    next_start = body.planned_start_at if "planned_start_at" in fields else task.planned_start_at
    next_end = body.planned_end_at if "planned_end_at" in fields else task.planned_end_at
    if next_start is not None and next_end is not None and next_end < next_start:
        raise HTTPException(status_code=422, detail="planned_end_at must be after planned_start_at")

    before = {
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "planned_start_at": task.planned_start_at.isoformat() if task.planned_start_at else None,
        "planned_end_at": task.planned_end_at.isoformat() if task.planned_end_at else None,
        "due_at": task.due_at.isoformat() if task.due_at else None,
    }

    if "title" in fields and body.title is not None:
        task.title = body.title.strip()
    if "description" in fields:
        task.description = body.description
    if "priority" in fields and body.priority is not None:
        task.priority = body.priority
    if "planned_start_at" in fields:
        task.planned_start_at = body.planned_start_at
    if "planned_end_at" in fields:
        task.planned_end_at = body.planned_end_at
    if "due_at" in fields:
        task.due_at = body.due_at
    if "status" in fields and body.status is not None:
        task.status = body.status
        if body.status in _ACTIVE and task.started_at is None:
            task.started_at = datetime.now(UTC)
        if body.status in _TERMINAL:
            task.completed_at = task.completed_at or datetime.now(UTC)
        elif task.completed_at is not None:
            task.completed_at = None

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="task.updated",
        aggregate_type="task",
        aggregate_id=task.id,
        correlation_id=correlation_id,
        payload={
            "task_id": str(task.id),
            "project_id": str(task.project_id),
            "status": task.status,
            "priority": task.priority,
            "planned_start_at": task.planned_start_at.isoformat() if task.planned_start_at else None,
            "planned_end_at": task.planned_end_at.isoformat() if task.planned_end_at else None,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=task.owner_ref,
        action="task.plan.update",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json", exclude_unset=True),
        result_json={"before": before},
    )
    await session.commit()
    await session.refresh(task)
    return task


@router.get("/v1/today", response_model=TodayRead)
async def today(
    timezone_offset_minutes: int = Query(default=0, ge=-840, le=840),
    limit_per_group: int = Query(default=24, ge=4, le=80),
    session: AsyncSession = Depends(get_session),
) -> TodayRead:
    start, end = _day_bounds(timezone_offset_minutes)
    result = await session.execute(
        select(Task)
        .where(_open_clause())
        .where(
            or_(
                Task.due_at < end,
                and_(Task.planned_start_at < end, or_(Task.planned_end_at.is_(None), Task.planned_end_at >= start)),
                Task.priority >= 3,
            )
        )
        .order_by(Task.priority.desc(), Task.due_at.asc().nulls_last(), Task.updated_at.desc())
        .limit(limit_per_group * 5)
    )
    rows = list(result.scalars())

    overdue: list[Task] = []
    due_today: list[Task] = []
    planned_today: list[Task] = []
    important: list[Task] = []
    assigned: set[uuid.UUID] = set()

    for task in rows:
        if task.due_at is not None and task.due_at < start:
            overdue.append(task)
            assigned.add(task.id)
    for task in rows:
        if task.id in assigned:
            continue
        if task.due_at is not None and start <= task.due_at < end:
            due_today.append(task)
            assigned.add(task.id)
    for task in rows:
        if task.id in assigned:
            continue
        if task.planned_start_at is not None and task.planned_start_at < end:
            effective_end = task.planned_end_at or task.planned_start_at
            if effective_end >= start:
                planned_today.append(task)
                assigned.add(task.id)
    for task in rows:
        if task.id not in assigned and task.priority >= 3:
            important.append(task)

    return TodayRead(
        generated_at=datetime.now(UTC),
        day_start=start,
        day_end=end,
        timezone_offset_minutes=timezone_offset_minutes,
        overdue=overdue[:limit_per_group],
        due_today=due_today[:limit_per_group],
        planned_today=planned_today[:limit_per_group],
        important=important[:limit_per_group],
    )
