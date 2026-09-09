from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select

from .auth import Principal, require_kairo_user
from .db import SessionFactory
from .graph_schemas import GraphActivityEventRead, GraphEntityRef
from .models import OutboxEvent
from .ownership import entity_belongs_to_subject


router = APIRouter(prefix="/v1/graph/activity", tags=["graph"])

_GRAPH_TYPES = {
    "project": "project",
    "projects": "project",
    "task": "task",
    "tasks": "task",
    "document": "document",
    "documents": "document",
    "conversation": "conversation",
    "conversations": "conversation",
    "approval": "approval",
    "approval_request": "approval",
    "approval_requests": "approval",
    "artifact": "artifact",
    "artifacts": "artifact",
    "asset": "asset",
    "assets": "asset",
    "workflow": "workflow_execution",
    "workflow_execution": "workflow_execution",
    "workflow_executions": "workflow_execution",
}

_PAYLOAD_ENTITY_KEYS = (
    ("project_id", "project"),
    ("task_id", "task"),
    ("document_id", "document"),
    ("conversation_id", "conversation"),
    ("approval_id", "approval"),
    ("artifact_id", "artifact"),
    ("asset_id", "asset"),
    ("workflow_execution_id", "workflow_execution"),
)


def _normalize_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _GRAPH_TYPES.get(normalized, normalized)


def _uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _ref(entity_type: str, entity_id: Any) -> GraphEntityRef | None:
    parsed = _uuid(entity_id)
    if parsed is None:
        return None
    normalized = _normalize_type(entity_type)
    if normalized not in set(_GRAPH_TYPES.values()):
        return None
    return GraphEntityRef(entity_type=normalized, entity_id=parsed)


def _append_unique(target: list[GraphEntityRef], value: GraphEntityRef | None) -> None:
    if value is None:
        return
    if any(item.entity_type == value.entity_type and item.entity_id == value.entity_id for item in target):
        return
    target.append(value)


def _payload_refs(payload: dict[str, Any]) -> list[GraphEntityRef]:
    refs: list[GraphEntityRef] = []
    for key, entity_type in _PAYLOAD_ENTITY_KEYS:
        _append_unique(refs, _ref(entity_type, payload.get(key)))
    return refs


def _activity_from_outbox(row: OutboxEvent) -> GraphActivityEventRead | None:
    payload = row.payload if isinstance(row.payload, dict) else {}
    related: list[GraphEntityRef] = []
    primary: GraphEntityRef | None = None

    aggregate_type = _normalize_type(row.aggregate_type)
    if aggregate_type == "relationship":
        source_type = payload.get("source_type")
        target_type = payload.get("target_type")
        if isinstance(source_type, str):
            primary = _ref(source_type, payload.get("source_id"))
        if isinstance(target_type, str):
            _append_unique(related, _ref(target_type, payload.get("target_id")))
    elif aggregate_type == "conversation_message":
        primary = _ref("conversation", payload.get("conversation_id"))
    elif aggregate_type in set(_GRAPH_TYPES.values()):
        primary = _ref(aggregate_type, row.aggregate_id)

    payload_refs = _payload_refs(payload)
    if primary is None and payload_refs:
        primary = payload_refs.pop(0)
    for value in payload_refs:
        if primary and value.entity_type == primary.entity_type and value.entity_id == primary.entity_id:
            continue
        _append_unique(related, value)

    if primary is None:
        return None

    return GraphActivityEventRead(
        id=row.id,
        event_type=row.event_type,
        entity=primary,
        related=related,
        correlation_id=row.correlation_id,
        occurred_at=row.created_at,
    )


async def _cursor_from_request(request: Request) -> tuple[datetime, uuid.UUID]:
    last_event_id = request.headers.get("last-event-id")
    if last_event_id:
        parsed = _uuid(last_event_id)
        if parsed:
            async with SessionFactory() as session:
                row = await session.get(OutboxEvent, parsed)
            if row is not None:
                created_at = row.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                return created_at, row.id
    return datetime.now(timezone.utc) - timedelta(seconds=5), uuid.UUID(int=0)


async def _owned_activity(
    session,
    activity: GraphActivityEventRead,
    subject: str,
) -> GraphActivityEventRead | None:
    if not await entity_belongs_to_subject(
        session,
        activity.entity.entity_type,
        activity.entity.entity_id,
        subject,
    ):
        return None
    related: list[GraphEntityRef] = []
    for ref in activity.related:
        if await entity_belongs_to_subject(
            session,
            ref.entity_type,
            ref.entity_id,
            subject,
        ):
            related.append(ref)
    activity.related = related
    return activity


@router.get("/stream")
async def stream_graph_activity(
    request: Request,
    principal: Principal = Depends(require_kairo_user),
) -> StreamingResponse:
    async def event_stream():
        cursor_time, cursor_id = await _cursor_from_request(request)
        idle_ticks = 0
        while not await request.is_disconnected():
            async with SessionFactory() as session:
                rows = await session.execute(
                    select(OutboxEvent)
                    .where(
                        or_(
                            OutboxEvent.created_at > cursor_time,
                            and_(
                                OutboxEvent.created_at == cursor_time,
                                OutboxEvent.id > cursor_id,
                            ),
                        )
                    )
                    .order_by(OutboxEvent.created_at.asc(), OutboxEvent.id.asc())
                    .limit(100)
                )
                events = list(rows.scalars())

                if events:
                    idle_ticks = 0
                    for row in events:
                        cursor_time = row.created_at
                        if cursor_time.tzinfo is None:
                            cursor_time = cursor_time.replace(tzinfo=timezone.utc)
                        cursor_id = row.id
                        activity = _activity_from_outbox(row)
                        if activity is None:
                            continue
                        activity = await _owned_activity(session, activity, principal.subject)
                        if activity is None:
                            continue
                        payload = json.dumps(
                            activity.model_dump(mode="json"), separators=(",", ":")
                        )
                        yield f"id: {row.id}\ndata: {payload}\n\n"
                else:
                    idle_ticks += 1
                    if idle_ticks >= 12:
                        idle_ticks = 0
                        yield ": keepalive\n\n"

            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
