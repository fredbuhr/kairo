import json
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select

from .config import settings
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditRecord, OutboxEvent


async def enqueue_domain_event(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: dict[str, Any],
    correlation_id: uuid.UUID,
) -> OutboxEvent:
    if len(json.dumps(payload, default=str, separators=(",", ":")).encode()) > settings.outbox_payload_max_bytes:
        raise HTTPException(422, "Domain event exceeds configured payload limit")
    # This rejection threshold may overshoot by bounded concurrent in-flight writes.
    # Never serialize unrelated domain row locks globally for this technical counter.
    pending = int(await session.scalar(select(func.count()).select_from(OutboxEvent).where(
        OutboxEvent.published_at.is_(None),
    )) or 0)
    if pending >= settings.outbox_max_pending:
        raise HTTPException(503, "Event backlog is full; retry after recovery", headers={"Retry-After": "5"})
    event = OutboxEvent(
        subject=f"kairo.domain.{event_type}",
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        correlation_id=correlation_id,
        payload=payload,
    )
    session.add(event)
    return event


async def append_audit(
    session: AsyncSession,
    *,
    actor_type: str,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    authority_level: int,
    correlation_id: uuid.UUID,
    request_json: dict[str, Any] | None = None,
    result_json: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> AuditRecord:
    record = AuditRecord(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        authority_level=authority_level,
        correlation_id=correlation_id,
        request_json=request_json or {},
        result_json=result_json or {},
        idempotency_key=idempotency_key,
    )
    session.add(record)
    return record
