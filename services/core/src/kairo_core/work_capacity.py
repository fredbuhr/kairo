"""Shared admission for CPU-heavy derived work; Temporal owns durable waiting."""
from datetime import datetime, timedelta
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Index, String, case, func, select, text, update
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .auth import Principal, require_kairo_user
from .command_models import Conversation, ConversationMessage
from .config import settings
from .db import Base, get_session
from .models import Project, Task
from .security import require_internal_token

router = APIRouter()
HEAVY_CAPABILITIES = {"document.ingest", "memory.project"}
LEASE_SECONDS = 660  # Above document wall time and independently bounded child lifetime.


class WorkAdmission(Base):
    __tablename__ = "work_admissions"
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    owner_subject: Mapped[str] = mapped_column(String(320), nullable=False)
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="waiting")
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lease_holder: Mapped[str | None] = mapped_column(String(320))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("ix_work_admission_owner", "owner_subject", "status", "created_at"),
        Index("ix_work_admission_lease", "status", "lease_until"),
    )


async def capacity_lock(session) -> None:
    if not await session.scalar(text("SELECT pg_try_advisory_xact_lock(1262572114, 3)")):
        raise HTTPException(429, "work_admission_busy", headers={"Retry-After": "5"})


async def ensure_work_request(session, task: Task) -> WorkAdmission | None:
    capability = str((task.input or {}).get("capability") or "")
    if capability not in HEAVY_CAPABILITIES:
        return None
    await capacity_lock(session)
    existing = await session.get(WorkAdmission, task.id)
    if existing:
        return existing
    # Memory uses a shared system Project; the real owner is the canonical conversation.
    if capability == "memory.project":
        source_id = uuid.UUID(str(task.input["source_id"]))
        owner = await session.scalar(select(Conversation.subject_ref).join(
            ConversationMessage, ConversationMessage.conversation_id == Conversation.id
        ).where(ConversationMessage.id == source_id))
    else:
        owner = await session.scalar(select(Project.owner_subject).where(Project.id == task.project_id))
    if not owner:
        raise HTTPException(409, "Heavy work requires canonical ownership")
    pending = select(func.count()).select_from(WorkAdmission).where(WorkAdmission.status != "finished")
    if int(await session.scalar(pending) or 0) >= settings.kairo_work_max_pending:
        raise HTTPException(429, "work_backlog_full", headers={"Retry-After": "5"})
    if int(await session.scalar(pending.where(WorkAdmission.owner_subject == owner)) or 0) >= settings.kairo_work_owner_max_pending:
        raise HTTPException(429, "owner_work_backlog_full", headers={"Retry-After": "5"})
    row = WorkAdmission(task_id=task.id, owner_subject=owner, capability=capability, status="waiting")
    session.add(row)
    await session.flush()
    return row


class WorkClaim(BaseModel):
    task_id: uuid.UUID
    holder: str = Field(min_length=1, max_length=320)


class WorkLease(BaseModel):
    task_id: uuid.UUID
    lease_token: uuid.UUID
    completed: bool = False
    result: dict | None = None


@router.post("/internal/v1/work-capacity/acquire", dependencies=[Depends(require_internal_token)])
async def acquire_work(body: WorkClaim, session=Depends(get_session)) -> dict:
    from .workflows import _require_execution_binding

    task = await session.get(Task, body.task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    await _require_execution_binding(task, session)
    row = await ensure_work_request(session, task)
    if row is None:
        raise HTTPException(409, "Task does not use heavy work admission")
    if row.status == "finished" and row.result_json:
        return {"admitted": True, "completed_result": row.result_json}
    if task.status in {"completed", "failed"} or row.status == "finished":
        raise HTTPException(409, "Task admission is terminal")
    now = await session.scalar(select(func.clock_timestamp()))
    await session.execute(update(WorkAdmission).where(
        WorkAdmission.status == "active", WorkAdmission.lease_until <= now,
    ).values(status="waiting", lease_token=None, lease_holder=None, lease_until=None))
    await session.refresh(row)
    if row.status == "active":
        if row.lease_holder == body.holder:
            return {"admitted": True, "lease_token": str(row.lease_token)}
        return {"admitted": False, "reason": "previous_attempt_active"}
    row.requested_at = now
    await session.flush()
    active = select(func.count()).select_from(WorkAdmission).where(WorkAdmission.status == "active")
    owner_active = select(WorkAdmission.owner_subject, func.count().label("n")).where(
        WorkAdmission.status == "active"
    ).group_by(WorkAdmission.owner_subject).subquery()
    eligible = await session.scalar(select(WorkAdmission.task_id).outerjoin(
        owner_active, owner_active.c.owner_subject == WorkAdmission.owner_subject
    ).where(
        WorkAdmission.status == "waiting", WorkAdmission.requested_at >= now - timedelta(seconds=30),
        func.coalesce(owner_active.c.n, 0) < settings.kairo_work_owner_concurrency,
    ).order_by(WorkAdmission.created_at, WorkAdmission.task_id).limit(1))
    admitted = int(await session.scalar(active) or 0) < settings.kairo_work_global_concurrency and eligible == row.task_id
    if admitted:
        row.status = "active"
        row.lease_token = uuid.uuid4()
        row.lease_holder = body.holder
        row.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        task.status = "running"
    else:
        task.status = "queued"
    await session.commit()
    return {"admitted": admitted, "lease_token": str(row.lease_token) if admitted else None,
            "reason": "admitted" if admitted else "waiting_for_capacity"}


async def require_work_lease(session, task_id: uuid.UUID, token: str | uuid.UUID | None) -> WorkAdmission:
    # A stale child may finish after a lease expires; it cannot publish authoritative results.
    try:
        token = uuid.UUID(str(token)) if token else None
    except ValueError as exc:
        raise HTTPException(409, "work_lease_lost") from exc
    row = await session.scalar(select(WorkAdmission).where(
        WorkAdmission.task_id == task_id, WorkAdmission.status == "active",
        WorkAdmission.lease_token == token, WorkAdmission.lease_until > func.clock_timestamp(),
    ).with_for_update()) if token else None
    if row is None:
        raise HTTPException(409, "work_lease_lost")
    return row


@router.post("/internal/v1/work-capacity/renew", dependencies=[Depends(require_internal_token)])
async def renew_work(body: WorkLease, session=Depends(get_session)) -> dict:
    row = await require_work_lease(session, body.task_id, body.lease_token)
    now = await session.scalar(select(func.clock_timestamp()))
    row.lease_until = now + timedelta(seconds=LEASE_SECONDS)
    await session.commit()
    return {"renewed": True}


@router.post("/internal/v1/work-capacity/release", dependencies=[Depends(require_internal_token)])
async def release_work(body: WorkLease, session=Depends(get_session)) -> dict:
    if body.completed and (not body.result or len(json.dumps(body.result).encode()) > 65536):
        raise HTTPException(422, "Completed work requires a bounded result")
    released = await session.scalar(update(WorkAdmission).where(
        WorkAdmission.task_id == body.task_id, WorkAdmission.status == "active",
        WorkAdmission.lease_token == body.lease_token,
        WorkAdmission.lease_until > func.clock_timestamp(),
    ).values(status="finished" if body.completed else "waiting", lease_token=None,
             lease_holder=None, lease_until=None, requested_at=None, result_json=body.result if body.completed else None,
             updated_at=func.now()).returning(WorkAdmission.task_id))
    if released is None and body.completed:
        row = await session.get(WorkAdmission, body.task_id)
        if not row or row.status != "finished" or row.result_json != body.result:
            raise HTTPException(409, "work_lease_lost")
    await session.commit()
    return {"released": released is not None or body.completed}


@router.get("/v1/work-capacity")
async def work_capacity(principal: Principal = Depends(require_kairo_user), session=Depends(get_session)) -> dict:
    visible_status = case((WorkAdmission.lease_until <= func.clock_timestamp(), "waiting"),
                          else_=WorkAdmission.status)
    rows = await session.execute(select(visible_status, func.count()).where(
        WorkAdmission.owner_subject == principal.subject, WorkAdmission.status != "finished",
    ).group_by(visible_status))
    counts = dict(rows.all())
    return {"waiting": counts.get("waiting", 0), "active": counts.get("active", 0),
            "concurrency_limit": settings.kairo_work_owner_concurrency,
            "pending_limit": settings.kairo_work_owner_max_pending}
