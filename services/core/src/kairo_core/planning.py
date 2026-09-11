from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .pagination import PageCursor, decode_cursor, encode_cursor
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Project, Task, WorkflowExecution
from .planning_schemas import PlannedTaskRead, TaskPlanningUpdate, TodayRead, TodayTaskItem
from .project_access import get_owned_task, owned_project_clause

router = APIRouter()


MANUAL_STATUSES = {"todo", "completed"}
ACTIVE_EXECUTION_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"completed", "failed"}


def _planning_window(day: date | None, timezone_name: str) -> tuple[date, ZoneInfo, datetime, datetime]:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Unknown IANA timezone") from exc

    local_day = day or datetime.now(zone).date()
    local_start = datetime.combine(local_day, time.min, tzinfo=zone)
    local_end = datetime.combine(local_day + timedelta(days=1), time.min, tzinfo=zone)
    return local_day, zone, local_start, local_end


def _task_read(task: Task) -> PlannedTaskRead:
    return PlannedTaskRead.model_validate(task)


def _item(bucket: str, task: Task, project: Project) -> TodayTaskItem:
    return TodayTaskItem(
        bucket=bucket,
        project_id=str(project.id),
        project_name=project.name,
        task=_task_read(task),
    )


@router.patch("/v1/tasks/{task_id}", response_model=PlannedTaskRead)
async def update_planned_task(
    task_id: uuid.UUID,
    body: TaskPlanningUpdate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Task:
    task = await get_owned_task(session, task_id, principal)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return task

    for required_field in ("title", "status", "priority"):
        if required_field in changes and changes[required_field] is None:
            raise HTTPException(status_code=422, detail=f"{required_field} cannot be null")

    if "status" in changes:
        new_status = str(changes["status"])
        if new_status not in MANUAL_STATUSES:
            raise HTTPException(status_code=422, detail="Unsupported manual Task status")
        existing_execution = await session.scalar(
            select(WorkflowExecution.id).where(WorkflowExecution.task_id == task.id).limit(1)
        )
        if existing_execution is not None:
            raise HTTPException(
                status_code=409,
                detail="Workflow-managed Task status cannot be changed manually",
            )

    planned_start = changes.get("planned_start_at", task.planned_start_at)
    planned_end = changes.get("planned_end_at", task.planned_end_at)
    if planned_end is not None and planned_start is None:
        raise HTTPException(status_code=422, detail="planned_end_at requires planned_start_at")
    if planned_start is not None and planned_end is not None and planned_end < planned_start:
        raise HTTPException(status_code=422, detail="planned_end_at must be on or after planned_start_at")

    correlation_id = uuid.uuid4()
    previous_status = task.status
    for field in (
        "title",
        "description",
        "priority",
        "planned_start_at",
        "planned_end_at",
        "due_at",
    ):
        if field in changes:
            setattr(task, field, changes[field])

    if "status" in changes:
        task.status = str(changes["status"])
        if task.status == "completed":
            task.completed_at = task.completed_at or datetime.now(UTC)
        elif task.status == "todo":
            task.completed_at = None
            task.started_at = None

    await session.flush()
    event_payload = {
        "task_id": str(task.id),
        "project_id": str(task.project_id),
        "changed_fields": sorted(changes),
        "status": task.status,
        "previous_status": previous_status,
        "priority": task.priority,
    }
    await enqueue_domain_event(
        session,
        event_type="task.updated",
        aggregate_type="task",
        aggregate_id=task.id,
        correlation_id=correlation_id,
        payload=event_payload,
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="task.update",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=min(task.authority_ceiling, 1),
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json", exclude_unset=True),
        result_json=event_payload,
    )
    await session.commit()
    await session.refresh(task)
    return task


@router.get("/v1/today", response_model=TodayRead)
async def today(
    day: date | None = Query(default=None),
    timezone_name: str = Query(default="UTC", alias="timezone", min_length=1, max_length=120),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    bucket: Literal["overdue", "in_progress", "due_today", "planned", "completed_today", "backlog"] | None = None,
    cursor: PageCursor = None,
) -> TodayRead:
    local_day, _zone, local_start, local_end = _planning_window(day, timezone_name)
    start_utc, end_utc = local_start.astimezone(UTC), local_end.astimezone(UTC)
    if cursor and not bucket:
        raise HTTPException(422, "A Today cursor requires its bucket")
    inactive = Task.status.notin_(TERMINAL_STATUSES | ACTIVE_EXECUTION_STATUSES)
    no_due_today = or_(Task.due_at.is_(None), Task.due_at >= end_utc)
    predicates = {
        "completed_today": and_(Task.status == "completed", Task.completed_at >= start_utc, Task.completed_at < end_utc),
        "in_progress": Task.status.in_(ACTIVE_EXECUTION_STATUSES),
        "overdue": and_(inactive, Task.due_at < start_utc),
        "due_today": and_(inactive, Task.due_at >= start_utc, Task.due_at < end_utc),
        "planned": and_(inactive, no_due_today, Task.planned_start_at < end_utc,
                        or_(Task.planned_end_at.is_(None), Task.planned_end_at >= start_utc)),
        "backlog": and_(Task.status == "todo", Task.due_at.is_(None), Task.planned_start_at.is_(None), Task.planned_end_at.is_(None)),
    }
    buckets = {key: [] for key in predicates}
    next_cursors = {}
    # A deterministic total order preserves priority and places undated Tasks last.
    far_future = datetime(9999, 1, 1, tzinfo=UTC)
    due_key = func.coalesce(Task.due_at, far_future)
    order_key = tuple_(-Task.priority, due_key, Task.created_at, Task.id)
    for name in ([bucket] if bucket else predicates):
        query = select(Task, Project).join(Project, Project.id == Task.project_id).where(
            owned_project_clause(principal), predicates[name],
        )
        if cursor:
            try:
                scope, priority, due, created, identity = decode_cursor(cursor, 5)
                if scope != f"{local_day}:{timezone_name}:{name}":
                    raise ValueError()
                due, created = datetime.fromisoformat(due), datetime.fromisoformat(created)
                if due.tzinfo is None or created.tzinfo is None:
                    raise ValueError()
                query = query.where(order_key > (int(priority), due, created, uuid.UUID(identity)))
            except (TypeError, ValueError) as exc:
                raise HTTPException(422, "Invalid Today cursor") from exc
        rows = list((await session.execute(query.order_by(
            Task.priority.desc(), due_key, Task.created_at, Task.id,
        ).limit(limit + 1))).all())
        if len(rows) > limit:
            last = rows[limit - 1][0]
            next_cursors[name] = encode_cursor([
                f"{local_day}:{timezone_name}:{name}", -last.priority,
                last.due_at or far_future, last.created_at, last.id,
            ])
        buckets[name] = [_item(name, task, project) for task, project in rows[:limit]]
    return TodayRead(day=local_day, timezone=timezone_name, day_start=local_start, day_end=local_end,
                     next_cursors=next_cursors, **buckets)
