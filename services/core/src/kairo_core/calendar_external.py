from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .calendar_models import CalendarSource, ExternalCalendarEvent
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .security import require_internal_token


router = APIRouter(tags=["calendar"])

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class CalendarSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    provider: str
    external_account_ref: str
    display_name: str
    status: str
    metadata_json: dict[str, Any]
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class ExternalCalendarEventRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_key: str
    source_provider: str
    source_display_name: str
    external_id: str
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    status: str
    location: str | None
    source_url: str | None
    metadata: dict[str, Any]
    source_updated_at: datetime | None
    observed_at: datetime


class CalendarSourceSnapshot(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    provider: str = Field(min_length=1, max_length=64)
    external_account_ref: str = Field(min_length=1, max_length=320)
    display_name: str = Field(min_length=1, max_length=240)
    status: str = Field(default="connected", min_length=1, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identity(self) -> "CalendarSourceSnapshot":
        self.key = self.key.strip().lower()
        self.provider = self.provider.strip().lower()
        self.external_account_ref = self.external_account_ref.strip()
        self.display_name = self.display_name.strip()
        self.status = self.status.strip().lower()
        if not _KEY_PATTERN.fullmatch(self.key):
            raise ValueError("calendar source key must use lowercase letters, digits, dots, underscores or hyphens")
        if not _KEY_PATTERN.fullmatch(self.provider):
            raise ValueError("calendar provider must use lowercase letters, digits, dots, underscores or hyphens")
        return self


class ExternalCalendarEventSnapshot(BaseModel):
    external_id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=512)
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    status: str = Field(default="confirmed", min_length=1, max_length=32)
    location: str | None = Field(default=None, max_length=512)
    source_url: str | None = Field(default=None, max_length=4096)
    source_updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_interval(self) -> "ExternalCalendarEventSnapshot":
        if self.start_at.utcoffset() is None or self.end_at.utcoffset() is None:
            raise ValueError("external calendar event timestamps must include timezone offsets")
        if self.end_at <= self.start_at:
            raise ValueError("external calendar event end_at must be after start_at")
        if self.source_updated_at is not None and self.source_updated_at.utcoffset() is None:
            raise ValueError("source_updated_at must include a timezone offset")
        self.external_id = self.external_id.strip()
        self.title = self.title.strip()
        self.status = self.status.strip().lower()
        return self


class CalendarSnapshotIngest(BaseModel):
    owner_subject: str = Field(min_length=1, max_length=240)
    source: CalendarSourceSnapshot
    events: list[ExternalCalendarEventSnapshot] = Field(default_factory=list, max_length=5000)
    replace_missing: bool = True

    @model_validator(mode="after")
    def validate_unique_external_ids(self) -> "CalendarSnapshotIngest":
        ids = [event.external_id for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("calendar snapshot contains duplicate external event ids")
        self.owner_subject = self.owner_subject.strip()
        return self


class CalendarSnapshotRead(BaseModel):
    source: CalendarSourceRead
    received_events: int
    removed_events: int
    observed_at: datetime


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.utcoffset() is None:
        raise HTTPException(status_code=422, detail=f"{label} must include a timezone offset")
    return value


async def _owned_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    principal: Principal,
) -> CalendarSource:
    source = await session.get(CalendarSource, source_id)
    if source is None or source.keycloak_subject != principal.subject:
        raise HTTPException(status_code=404, detail="Calendar source not found")
    return source


@router.get("/v1/calendar/sources", response_model=list[CalendarSourceRead])
async def list_calendar_sources(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[CalendarSource]:
    rows = await session.execute(
        select(CalendarSource)
        .where(CalendarSource.keycloak_subject == principal.subject)
        .order_by(CalendarSource.display_name, CalendarSource.key)
    )
    return list(rows.scalars())


@router.get("/v1/calendar/external-events", response_model=list[ExternalCalendarEventRead])
async def list_external_calendar_events(
    start: datetime,
    end: datetime,
    source_id: uuid.UUID | None = None,
    include_cancelled: bool = Query(default=False),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[ExternalCalendarEventRead]:
    start = _require_aware(start, label="start")
    end = _require_aware(end, label="end")
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be after start")

    if source_id is not None:
        await _owned_source(session, source_id, principal)

    statement = (
        select(ExternalCalendarEvent, CalendarSource)
        .join(CalendarSource, CalendarSource.id == ExternalCalendarEvent.source_id)
        .where(CalendarSource.keycloak_subject == principal.subject)
        .where(ExternalCalendarEvent.start_at < end, ExternalCalendarEvent.end_at > start)
        .order_by(ExternalCalendarEvent.start_at, ExternalCalendarEvent.title)
    )
    if source_id is not None:
        statement = statement.where(ExternalCalendarEvent.source_id == source_id)
    if not include_cancelled:
        statement = statement.where(ExternalCalendarEvent.status != "cancelled")

    rows = await session.execute(statement)
    return [
        ExternalCalendarEventRead(
            id=event.id,
            source_id=source.id,
            source_key=source.key,
            source_provider=source.provider,
            source_display_name=source.display_name,
            external_id=event.external_id,
            title=event.title,
            start_at=event.start_at,
            end_at=event.end_at,
            all_day=event.all_day,
            status=event.status,
            location=event.location,
            source_url=event.source_url,
            metadata=dict(event.metadata_json or {}),
            source_updated_at=event.source_updated_at,
            observed_at=event.observed_at,
        )
        for event, source in rows
    ]


@router.post(
    "/internal/v1/calendar/snapshot",
    response_model=CalendarSnapshotRead,
    dependencies=[Depends(require_internal_token)],
)
async def ingest_calendar_snapshot(
    body: CalendarSnapshotIngest,
    session: AsyncSession = Depends(get_session),
) -> CalendarSnapshotRead:
    source = await session.scalar(
        select(CalendarSource)
        .where(
            CalendarSource.keycloak_subject == body.owner_subject,
            CalendarSource.key == body.source.key,
        )
        .with_for_update()
    )

    if source is None:
        account_binding = await session.scalar(
            select(CalendarSource).where(
                CalendarSource.keycloak_subject == body.owner_subject,
                CalendarSource.provider == body.source.provider,
                CalendarSource.external_account_ref == body.source.external_account_ref,
            )
        )
        if account_binding is not None:
            raise HTTPException(
                status_code=409,
                detail="Calendar account is already bound to another source key",
            )
        source = CalendarSource(
            keycloak_subject=body.owner_subject,
            key=body.source.key,
            provider=body.source.provider,
            external_account_ref=body.source.external_account_ref,
            display_name=body.source.display_name,
            status=body.source.status,
            metadata_json=body.source.metadata,
        )
        session.add(source)
        await session.flush()
    elif (
        source.provider != body.source.provider
        or source.external_account_ref != body.source.external_account_ref
    ):
        raise HTTPException(
            status_code=409,
            detail="Calendar source key cannot be rebound to a different external account",
        )

    observed_at = datetime.now(UTC)
    source.display_name = body.source.display_name
    source.status = body.source.status
    source.metadata_json = body.source.metadata
    source.last_sync_at = observed_at
    source.last_error = None

    external_ids = [event.external_id for event in body.events]
    existing: dict[str, ExternalCalendarEvent] = {}
    if external_ids:
        rows = await session.execute(
            select(ExternalCalendarEvent).where(
                ExternalCalendarEvent.source_id == source.id,
                ExternalCalendarEvent.external_id.in_(external_ids),
            )
        )
        existing = {event.external_id: event for event in rows.scalars()}

    for item in body.events:
        event = existing.get(item.external_id)
        if event is None:
            event = ExternalCalendarEvent(
                id=uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"kairo:calendar:{source.id}:{item.external_id}",
                ),
                source_id=source.id,
                external_id=item.external_id,
                title=item.title,
                start_at=item.start_at,
                end_at=item.end_at,
                all_day=item.all_day,
                status=item.status,
                location=item.location,
                source_url=item.source_url,
                metadata_json=item.metadata,
                source_updated_at=item.source_updated_at,
                observed_at=observed_at,
            )
            session.add(event)
        else:
            event.title = item.title
            event.start_at = item.start_at
            event.end_at = item.end_at
            event.all_day = item.all_day
            event.status = item.status
            event.location = item.location
            event.source_url = item.source_url
            event.metadata_json = item.metadata
            event.source_updated_at = item.source_updated_at
            event.observed_at = observed_at

    removed_events = 0
    if body.replace_missing:
        delete_statement = delete(ExternalCalendarEvent).where(
            ExternalCalendarEvent.source_id == source.id
        )
        if external_ids:
            delete_statement = delete_statement.where(
                ~ExternalCalendarEvent.external_id.in_(external_ids)
            )
        result = await session.execute(delete_statement)
        removed_events = int(result.rowcount or 0)

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="calendar.source.synced",
        aggregate_type="calendar_source",
        aggregate_id=source.id,
        correlation_id=correlation_id,
        payload={
            "calendar_source_id": str(source.id),
            "provider": source.provider,
            "received_events": len(body.events),
            "removed_events": removed_events,
            "observed_at": observed_at.isoformat(),
        },
    )
    await append_audit(
        session,
        actor_type="connector",
        actor_id=f"calendar:{source.provider}",
        action="calendar.snapshot.ingest",
        resource_type="calendar_source",
        resource_id=str(source.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "owner_subject": body.owner_subject,
            "source_key": source.key,
            "provider": source.provider,
            "event_count": len(body.events),
            "replace_missing": body.replace_missing,
        },
        result_json={"removed_events": removed_events},
    )
    await session.commit()
    await session.refresh(source)

    return CalendarSnapshotRead(
        source=CalendarSourceRead.model_validate(source),
        received_events=len(body.events),
        removed_events=removed_events,
        observed_at=observed_at,
    )
