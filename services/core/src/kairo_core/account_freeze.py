from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_lifecycle_models import AccountWriteFreeze
from .auth import Principal, require_kairo_user
from .db import get_session
from .events import append_audit, enqueue_domain_event

router = APIRouter(prefix="/v1/account/erasure/write-freeze", tags=["account-lifecycle"])

# A frozen browser identity may still drive only these explicitly bounded erasure-preparation writes.
# Ordinary domain writes stay locked. Future destructive orchestration should prefer internal durable
# operations rather than progressively broadening this allow-list.
_FROZEN_WRITE_ALLOWLIST = frozenset(
    {
        "/v1/account/erasure/write-freeze",
        "/v1/account/erasure/write-freeze/cancel",
        "/v1/account/evidence/retention/apply",
        "/v1/account/derived-memory/purge",
    }
)


class AccountWriteFreezeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    frozen: bool
    operation_id: uuid.UUID | None = None
    reason: str | None = None
    frozen_at: datetime | None = None
    updated_at: datetime | None = None
    blocks_public_mutations: Literal[True] = True
    keycloak_identity_changed: Literal[False] = False


class AccountWriteFreezeCreate(BaseModel):
    confirmation: Literal["FREEZE_ACCOUNT_WRITES"]
    reason: str = Field(default="account_erasure_preparation", min_length=1, max_length=320)


class AccountWriteFreezeCancel(BaseModel):
    confirmation: Literal["UNFREEZE_ACCOUNT_WRITES"]


def frozen_public_write_allowed(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return normalized in _FROZEN_WRITE_ALLOWLIST


async def get_account_write_freeze(
    session: AsyncSession,
    subject: str,
    *,
    lock: bool = False,
) -> AccountWriteFreeze | None:
    statement = select(AccountWriteFreeze).where(AccountWriteFreeze.keycloak_subject == subject)
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def account_writes_frozen(session: AsyncSession, subject: str) -> bool:
    return await get_account_write_freeze(session, subject) is not None


def _read(row: AccountWriteFreeze | None) -> AccountWriteFreezeRead:
    if row is None:
        return AccountWriteFreezeRead(frozen=False)
    return AccountWriteFreezeRead(
        frozen=True,
        operation_id=row.operation_id,
        reason=row.reason,
        frozen_at=row.frozen_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=AccountWriteFreezeRead)
async def read_account_write_freeze(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> AccountWriteFreezeRead:
    return _read(await get_account_write_freeze(session, principal.subject))


@router.post("", response_model=AccountWriteFreezeRead, status_code=status.HTTP_201_CREATED)
async def freeze_account_writes(
    body: AccountWriteFreezeCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> AccountWriteFreezeRead:
    existing = await get_account_write_freeze(session, principal.subject, lock=True)
    if existing is not None:
        return _read(existing)

    reason = body.reason.strip()
    row = AccountWriteFreeze(
        keycloak_subject=principal.subject,
        operation_id=uuid.uuid4(),
        reason=reason,
    )
    session.add(row)
    await session.flush()

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="account.write_frozen",
        aggregate_type="account_write_freeze",
        aggregate_id=row.operation_id,
        correlation_id=correlation_id,
        keycloak_subject=principal.subject,
        payload={
            "operation_id": str(row.operation_id),
            "state": "frozen",
            "reason": reason,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="account.write_freeze",
        resource_type="account_write_freeze",
        resource_id=str(row.operation_id),
        authority_level=1,
        correlation_id=correlation_id,
        keycloak_subject=principal.subject,
        request_json={"reason": reason},
        result_json={"state": "frozen"},
    )
    await session.commit()
    await session.refresh(row)
    return _read(row)


@router.post("/cancel", response_model=AccountWriteFreezeRead)
async def cancel_account_write_freeze(
    _: AccountWriteFreezeCancel,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> AccountWriteFreezeRead:
    row = await get_account_write_freeze(session, principal.subject, lock=True)
    if row is None:
        return AccountWriteFreezeRead(frozen=False)

    operation_id = row.operation_id
    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="account.write_unfrozen",
        aggregate_type="account_write_freeze",
        aggregate_id=operation_id,
        correlation_id=correlation_id,
        keycloak_subject=principal.subject,
        payload={"operation_id": str(operation_id), "state": "active"},
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="account.write_unfreeze",
        resource_type="account_write_freeze",
        resource_id=str(operation_id),
        authority_level=1,
        correlation_id=correlation_id,
        keycloak_subject=principal.subject,
        result_json={"state": "active"},
    )
    await session.delete(row)
    await session.commit()
    return AccountWriteFreezeRead(frozen=False)


async def require_account_not_frozen(session: AsyncSession, subject: str) -> None:
    if await account_writes_frozen(session, subject):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account writes are frozen for erasure preparation",
        )
