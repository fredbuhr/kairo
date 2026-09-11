"""Short PostgreSQL transactions own model capacity, estimates and one-shot dispatch.

No lock is held across provider I/O. Expiry releases capacity, never invents a zero
cost for a request that may have reached a provider. Unknown liability is retained
until the canonical usage handoff can settle it.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from .autonomy_models import ModelReservation, ModelUsageRecord
from .auth import Principal, require_nevolium_user
from .config import settings
from .db import get_session
from .models import Project, Task
from .security import require_internal_token

router = APIRouter()
RESERVATION_TTL = timedelta(seconds=60)
DISPATCH_TTL = timedelta(seconds=300)
ACTIVE = ("reserved", "started")


async def lock_admission(session: AsyncSession) -> None:
    # Transaction-scoped and shared by every Core replica. A busy admission endpoint
    # refuses explicitly rather than consuming the entire DB pool while waiting.
    if not await session.scalar(text("SELECT pg_try_advisory_xact_lock(1262572114, 2)")):
        raise HTTPException(429, "model_admission_busy", headers={"Retry-After": "1"})


async def expire_reservations(session: AsyncSession) -> None:
    now = func.clock_timestamp()
    await session.execute(update(ModelReservation).where(
        ModelReservation.status == "reserved", ModelReservation.expires_at <= now
    ).values(status="expired"))
    await session.execute(update(ModelReservation).where(
        ModelReservation.status == "started", ModelReservation.expires_at <= now
    ).values(status="uncertain"))


def liability_clause():
    return or_(
        ModelReservation.status.in_(("started", "uncertain")),
        and_(ModelReservation.status == "reserved", ModelReservation.expires_at > func.now()),
    )


async def task_exposure(session: AsyncSession, task_id: uuid.UUID) -> dict:
    # One SQL statement provides one snapshot even during concurrent settlement.
    spent = select(func.coalesce(func.sum(ModelUsageRecord.cost_usd), 0)).where(
        ModelUsageRecord.task_id == task_id
    ).scalar_subquery()
    uncertain = or_(
        ModelReservation.status == "uncertain",
        and_(ModelReservation.status == "started", ModelReservation.expires_at <= func.now()),
    )
    row = (await session.execute(select(
        spent.label("spent"),
        func.coalesce(func.sum(case((uncertain, ModelReservation.amount_usd), else_=0)), 0).label("uncertain"),
        func.coalesce(func.sum(case((~uncertain, ModelReservation.amount_usd), else_=0)), 0).label("reserved"),
        func.count().filter(uncertain).label("uncertain_calls"),
    ).where(ModelReservation.task_id == task_id, liability_clause()))).one()
    return dict(row._mapping)


async def daily_exposure(session: AsyncSession, owner: str | None = None) -> Decimal:
    # Outstanding liability crosses midnight; only settled spend resets each UTC day.
    day_start = func.date_trunc("day", func.timezone("UTC", func.now())).op("AT TIME ZONE")("UTC")
    spend = select(func.coalesce(func.sum(ModelUsageRecord.cost_usd), 0)).select_from(
        ModelUsageRecord
    ).join(Task, Task.id == ModelUsageRecord.task_id).join(Project, Project.id == Task.project_id).where(
        ModelUsageRecord.created_at >= day_start
    )
    pending = select(func.coalesce(func.sum(ModelReservation.amount_usd), 0)).where(liability_clause())
    if owner is not None:
        spend = spend.where(func.coalesce(Project.owner_subject, "") == owner)
        pending = pending.where(ModelReservation.owner_subject == owner)
    return Decimal(await session.scalar(select(spend.scalar_subquery() + pending.scalar_subquery())))


async def reserve_model_call(
    session: AsyncSession, *, task: Task, key: str, execution_id: uuid.UUID | None,
    model_alias: str, amount: Decimal,
) -> str | None:
    if model_alias != "local-fast" and amount <= 0:
        return "paid_model_requires_positive_estimate"
    existing = await session.get(ModelReservation, key)
    if existing:
        if (existing.task_id, existing.workflow_execution_id, existing.model_alias) != (task.id, execution_id, model_alias):
            raise HTTPException(409, "model_reservation_binding_mismatch")
        if existing.status not in ("reserved", "expired"):
            return "model_call_already_dispatched"
        if existing.amount_usd != amount.quantize(Decimal("0.000001"), rounding=ROUND_CEILING):
            raise HTTPException(409, "model_reservation_estimate_mismatch")
        if existing.status == "reserved":
            return None  # Lost reserve response is safe; dispatch still needs one-shot claim.
    if await session.scalar(select(ModelUsageRecord.id).where(ModelUsageRecord.idempotency_key == key)):
        return "model_call_already_accounted"
    project = await session.get(Project, task.project_id)
    owner = project.owner_subject or ""
    live = select(func.count()).select_from(ModelReservation).where(ModelReservation.status.in_(ACTIVE))
    if await session.scalar(live) >= settings.nevolium_model_global_concurrency:
        raise HTTPException(429, "model_global_capacity_exhausted", headers={"Retry-After": "1"})
    if await session.scalar(live.where(ModelReservation.owner_subject == owner)) >= settings.nevolium_model_owner_concurrency:
        raise HTTPException(429, "model_owner_capacity_exhausted", headers={"Retry-After": "1"})
    amount = amount.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
    exposure = await task_exposure(session, task.id)
    if task.budget_usd is not None and sum(exposure[k] for k in ("spent", "reserved", "uncertain")) + amount > task.budget_usd:
        return "hard_budget_exceeded"
    if await daily_exposure(session) + amount > settings.nevolium_model_global_daily_budget_usd:
        return "model_global_daily_budget_exceeded"
    if await daily_exposure(session, owner) + amount > settings.nevolium_model_owner_daily_budget_usd:
        return "model_owner_daily_budget_exceeded"
    now = await session.scalar(select(func.clock_timestamp()))
    if existing is not None:  # A never-dispatched expired reservation is safe to admit again.
        existing.status = "reserved"
        existing.expires_at = now + RESERVATION_TTL
    else:
        session.add(ModelReservation(
            idempotency_key=key, task_id=task.id, workflow_execution_id=execution_id,
            owner_subject=owner, model_alias=model_alias, amount_usd=amount,
            status="reserved", expires_at=now + RESERVATION_TTL,
        ))
    await session.flush()
    return None


@router.get("/v1/model-admission")
async def owner_admission(
    principal: Principal = Depends(require_nevolium_user), session: AsyncSession = Depends(get_session),
) -> dict:
    active = await session.scalar(select(func.count()).select_from(ModelReservation).where(
        ModelReservation.owner_subject == principal.subject,
        ModelReservation.status.in_(ACTIVE), ModelReservation.expires_at > func.now(),
    ))
    return {"active_calls": active, "concurrency_limit": settings.nevolium_model_owner_concurrency,
            "daily_exposure_usd": str(await daily_exposure(session, principal.subject)),
            "daily_budget_usd": str(settings.nevolium_model_owner_daily_budget_usd)}


class ModelDispatch(BaseModel):
    task_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/internal/v1/model-reservations/start", dependencies=[Depends(require_internal_token)])
async def start_model_call(body: ModelDispatch, session: AsyncSession = Depends(get_session)) -> dict:
    await lock_admission(session)
    await expire_reservations(session)
    reservation = await session.get(ModelReservation, body.idempotency_key)
    if not reservation or reservation.task_id != body.task_id:
        raise HTTPException(404, "Model reservation not found")
    if reservation.status != "reserved":
        raise HTTPException(409, "model_call_dispatch_not_repeatable")
    now = await session.scalar(select(func.clock_timestamp()))
    reservation.status = "started"
    reservation.expires_at = now + DISPATCH_TTL
    await session.commit()
    return {"started": True, "idempotency_key": body.idempotency_key}


async def settle_reservation(session: AsyncSession, *, key: str | None, task: Task,
                             execution_id: uuid.UUID | None, model_alias: str,
                             cost: Decimal, cost_reported: bool) -> dict:
    if not key:
        return {}  # Pre-D02 accounting remains readable/replayable during a drained upgrade.
    reservation = await session.get(ModelReservation, key)
    if reservation is None:
        return {}
    if (reservation.task_id, reservation.workflow_execution_id, reservation.model_alias) != (task.id, execution_id, model_alias):
        raise HTTPException(409, "model_reservation_binding_mismatch")
    if reservation.status not in ("started", "uncertain"):
        raise HTTPException(409, "model_reservation_not_dispatched")
    evidence = {"reserved_estimate_usd": str(reservation.amount_usd),
                "estimate_exceeded": cost > reservation.amount_usd,
                "cost_reported": cost_reported}
    reservation.status = "settled" if cost_reported else "uncertain"
    if cost_reported:
        reservation.amount_usd = Decimal("0")
    else:
        # Count any known debit only once, retain the unresolved remainder.
        reservation.amount_usd = max(Decimal("0"), reservation.amount_usd - cost)
    return evidence
