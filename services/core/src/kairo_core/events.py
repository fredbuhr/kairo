import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .event_ownership import resolve_data_subject
from .models import AuditRecord, OutboxEvent


async def enqueue_domain_event(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: dict[str, Any],
    correlation_id: uuid.UUID,
    keycloak_subject: str | None = None,
) -> OutboxEvent:
    owner = keycloak_subject
    if owner is None:
        owner = await resolve_data_subject(session, aggregate_type, aggregate_id)
    event = OutboxEvent(
        keycloak_subject=owner,
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
    keycloak_subject: str | None = None,
) -> AuditRecord:
    owner = keycloak_subject
    if owner is None:
        owner = await resolve_data_subject(session, resource_type, resource_id)
    record = AuditRecord(
        keycloak_subject=owner,
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
