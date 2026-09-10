from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
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
) -> TodayRead:
    local_day, _zone, local_start, local_end = _planning_window(day, timezone_name)
    start_utc = local_start.astimezone(UTC)
    end_utc = local_end.astimezone(UTC)

    incomplete = Task.status.notin_(TERMINAL_STATUSES)
    planned_overlap = and_(
        incomplete,
        Task.planned_start_at.is_not(None),
        Task.planned_start_at < end_utc,
        or_(Task.planned_end_at.is_(None), Task.planned_end_at >= start_utc),
    )
    rows = await session.execute(
        select(Task, Project)
        .join(Project, Project.id == Task.project_id)
        .where(owned_project_clause(principal))
        .where(
            or_(
                Task.status.in_(ACTIVE_EXECUTION_STATUSES),
                and_(
                    Task.status == "completed",
                    Task.completed_at.is_not(None),
                    Task.completed_at >= start_utc,
                    Task.completed_at < end_utc,
                ),
                and_(incomplete, Task.due_at.is_not(None), Task.due_at < end_utc),
                planned_overlap,
                and_(
                    Task.status == "todo",
                    Task.due_at.is_(None),
                    Task.planned_start_at.is_(None),
                    Task.planned_end_at.is_(None),
                ),
            )
        )
        .order_by(Task.priority.desc(), Task.due_at.asc().nullslast(), Task.created_at.asc())
    )

    buckets: dict[str, list[TodayTaskItem]] = {
        "overdue": [],
        "in_progress": [],
        "due_today": [],
        "planned": [],
        "completed_today": [],
        "backlog": [],
    }

    for task, project in rows.all():
        if (
            task.status == "completed"
            and task.completed_at is not None
            and start_utc <= task.completed_at < end_utc
        ):
            buckets["completed_today"].append(_item("completed_today", task, project))
            continue
        if task.status in ACTIVE_EXECUTION_STATUSES:
            buckets["in_progress"].append(_item("in_progress", task, project))
            continue
        if task.status in TERMINAL_STATUSES:
            continue
        if task.due_at is not None and task.due_at < start_utc:
            buckets["overdue"].append(_item("overdue", task, project))
            continue
        if task.due_at is not None and task.due_at < end_utc:
            buckets["due_today"].append(_item("due_today", task, project))
            continue
        if (
            task.planned_start_at is not None
            and task.planned_start_at < end_utc
            and (task.planned_end_at is None or task.planned_end_at >= start_utc)
        ):
            buckets["planned"].append(_item("planned", task, project))
            continue
        if (
            task.status == "todo"
            and task.due_at is None
            and task.planned_start_at is None
            and task.planned_end_at is None
            and len(buckets["backlog"]) < 20
        ):
            buckets["backlog"].append(_item("backlog", task, project))

    return TodayRead(
        day=local_day,
        timezone=timezone_name,
        day_start=local_start,
        day_end=local_end,
        overdue=buckets["overdue"],
        in_progress=buckets["in_progress"],
        due_today=buckets["due_today"],
        planned=buckets["planned"],
        completed_today=buckets["completed_today"],
        backlog=buckets["backlog"],
    )
