from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_nevolium_user
from .command_models import Conversation, ConversationMessage
from .db import get_session
from .work_capacity import ensure_work_request, require_work_lease
from .events import append_audit, enqueue_domain_event
from .memory_models import MemoryProjectionRecord
from .models import AuditRecord, Project, Task
from .pagination import decode_cursor, encode_cursor
from .security import require_internal_token, require_operations_token

router = APIRouter()

MEMORY_PROJECT_ID = uuid.uuid5(uuid.NAMESPACE_URL, "nevolium:project:memory")
MEMORY_SOURCE_TYPE = "conversation_message"
MEMORY_SOURCE_VERSION = 1
MEMORY_PROJECTORS = ("mem0", "graphiti")


def _task_id(message_id: uuid.UUID, generation: int) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"nevolium:memory:conversation-message:{message_id}:v{MEMORY_SOURCE_VERSION}:g{generation}",
    )


def _projection_snapshot(row: MemoryProjectionRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "source_version": row.source_version,
        "projector": row.projector,
        "generation": row.generation,
        "status": row.status,
        "task_id": row.task_id,
        "projection_key": row.projection_key,
        "metadata": row.metadata_json,
        "last_error": row.last_error,
        "projected_at": row.projected_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def _ensure_memory_project(session: AsyncSession) -> Project:
    inserted_id = await session.scalar(
        pg_insert(Project)
        .values(
            id=MEMORY_PROJECT_ID,
            name="Nevolium Memory",
            status="active",
            summary="System workspace for rebuildable Mem0 and Graphiti projections.",
            parent_id=None,
        )
        .on_conflict_do_nothing(index_elements=[Project.id])
        .returning(Project.id)
    )
    project = await session.get(Project, MEMORY_PROJECT_ID)
    if project is None:
        raise RuntimeError("Nevolium Memory workspace could not be initialized")
    if inserted_id is not None:
        correlation_id = uuid.uuid4()
        await enqueue_domain_event(
            session,
            event_type="project.created",
            aggregate_type="project",
            aggregate_id=project.id,
            correlation_id=correlation_id,
            payload={"project_id": str(project.id), "name": project.name, "status": project.status},
        )
        await append_audit(
            session,
            actor_type="system",
            actor_id="memory-projector",
            action="project.create",
            resource_type="project",
            resource_id=str(project.id),
            authority_level=0,
            correlation_id=correlation_id,
            request_json={"reason": "initialize rebuildable memory workspace"},
        )
    return project


async def _projection_rows(
    session: AsyncSession,
    message_id: uuid.UUID,
    *,
    lock: bool = False,
) -> list[MemoryProjectionRecord]:
    query = (
        select(MemoryProjectionRecord)
        .where(
            MemoryProjectionRecord.source_type == MEMORY_SOURCE_TYPE,
            MemoryProjectionRecord.source_id == message_id,
            MemoryProjectionRecord.source_version == MEMORY_SOURCE_VERSION,
        )
        .order_by(MemoryProjectionRecord.projector)
    )
    if lock:
        query = query.with_for_update()
    result = await session.execute(query)
    return list(result.scalars())


async def _seed_projection_rows(
    session: AsyncSession,
    message_id: uuid.UUID,
    generation: int,
) -> int:
    created = 0
    for projector in MEMORY_PROJECTORS:
        inserted = await session.scalar(
            pg_insert(MemoryProjectionRecord)
            .values(
                id=uuid.uuid4(),
                source_type=MEMORY_SOURCE_TYPE,
                source_id=message_id,
                source_version=MEMORY_SOURCE_VERSION,
                projector=projector,
                generation=generation,
                status="pending",
                metadata_json={},
            )
            .on_conflict_do_nothing(
                index_elements=[
                    MemoryProjectionRecord.source_type,
                    MemoryProjectionRecord.source_id,
                    MemoryProjectionRecord.source_version,
                    MemoryProjectionRecord.projector,
                ]
            )
            .returning(MemoryProjectionRecord.id)
        )
        created += int(inserted is not None)
    await session.flush()
    return created


async def _conversation_for_message(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> tuple[ConversationMessage, Conversation]:
    message = await session.get(ConversationMessage, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation message not found")
    conversation = await session.get(Conversation, message.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return message, conversation


@router.get(
    "/internal/v1/memory/sources/conversation-messages/{message_id}",
    dependencies=[Depends(require_internal_token)],
)
async def canonical_memory_source(
    message_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    message, conversation = await _conversation_for_message(session, message_id)
    return {
        "source_type": MEMORY_SOURCE_TYPE,
        "source_version": MEMORY_SOURCE_VERSION,
        "message_id": message.id,
        "conversation_id": conversation.id,
        "subject_ref": conversation.subject_ref,
        "locale": conversation.locale,
        "role": message.role,
        "content": message.content,
        "metadata": message.metadata_json,
        "created_at": message.created_at,
    }


@router.post(
    "/internal/v1/memory/projections/conversation-messages/{message_id}/ensure",
    dependencies=[Depends(require_internal_token)],
)
async def ensure_memory_projection(
    message_id: uuid.UUID,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    message = await session.get(ConversationMessage, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation message not found")

    try:
        requested_generation = max(1, int(body.get("generation") or 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="generation must be a positive integer") from None

    await _seed_projection_rows(session, message_id, requested_generation)
    rows = await _projection_rows(session, message_id, lock=True)
    current_generation = max((row.generation for row in rows), default=0)

    if current_generation > requested_generation:
        await session.commit()
        return {
            "message_id": message_id,
            "generation": current_generation,
            "requested_generation": requested_generation,
            "status": "superseded",
            "should_run": False,
            "task_id": None,
        }

    if current_generation < requested_generation:
        for row in rows:
            row.generation = requested_generation
            row.status = "pending"
            row.task_id = None
            row.projection_key = None
            row.metadata_json = {}
            row.last_error = None
            row.projected_at = None

    if rows and all(
        row.generation == requested_generation and row.status == "projected" for row in rows
    ):
        await session.commit()
        return {
            "message_id": message_id,
            "generation": requested_generation,
            "status": "projected",
            "should_run": False,
            "task_id": rows[0].task_id,
        }

    project = await _ensure_memory_project(session)
    task_id = _task_id(message_id, requested_generation)
    inserted_task_id = await session.scalar(
        pg_insert(Task)
        .values(
            id=task_id,
            project_id=project.id,
            title=f"Project conversation memory — {message_id}",
            description=(
                "Rebuildable projection of one canonical ConversationMessage into Mem0 and "
                "Graphiti/Neo4j."
            ),
            status="todo",
            owner_type="system",
            owner_ref="memory-projector",
            authority_ceiling=1,
            budget_usd=Decimal("0"),
            input={
                "capability": "memory.project",
                "authority_level": 1,
                "estimated_cost_usd": "0",
                "source_type": MEMORY_SOURCE_TYPE,
                "source_id": str(message_id),
                "source_version": MEMORY_SOURCE_VERSION,
                "projection_generation": requested_generation,
                "projectors": list(MEMORY_PROJECTORS),
            },
        )
        .on_conflict_do_nothing(index_elements=[Task.id])
        .returning(Task.id)
    )
    task = await session.get(Task, task_id)
    if task is None:
        raise RuntimeError("Memory projection Task could not be initialized")
    await ensure_work_request(session, task)

    for row in rows:
        if row.generation == requested_generation:
            row.task_id = task.id

    correlation_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"nevolium:memory-projection:{message_id}:v{MEMORY_SOURCE_VERSION}:g{requested_generation}",
    )
    if inserted_task_id is not None:
        await enqueue_domain_event(
            session,
            event_type="memory.projection.requested",
            aggregate_type="conversation_message",
            aggregate_id=message_id,
            correlation_id=correlation_id,
            payload={
                "message_id": str(message_id),
                "task_id": str(task.id),
                "generation": requested_generation,
                "projectors": list(MEMORY_PROJECTORS),
            },
        )
        await append_audit(
            session,
            actor_type="system",
            actor_id="memory-projector",
            action="memory.projection.request",
            resource_type="conversation_message",
            resource_id=str(message_id),
            authority_level=1,
            correlation_id=correlation_id,
            idempotency_key=(
                f"memory:{message_id}:v{MEMORY_SOURCE_VERSION}:g{requested_generation}:request"
            ),
            request_json={"task_id": str(task.id), "projectors": list(MEMORY_PROJECTORS)},
        )

    await session.commit()
    return {
        "message_id": message_id,
        "generation": requested_generation,
        "status": task.status,
        "should_run": task.status not in {"completed", "failed"},
        "task_id": task.id,
    }


@router.post(
    "/internal/v1/memory/projections/conversation-messages/{message_id}/report",
    dependencies=[Depends(require_internal_token)],
)
async def report_memory_projection(
    message_id: uuid.UUID,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        generation = max(1, int(body.get("generation") or 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="generation must be a positive integer") from None

    reports = body.get("projectors")
    if not isinstance(reports, list) or not reports:
        raise HTTPException(status_code=422, detail="projectors report list is required")

    rows = await _projection_rows(session, message_id, lock=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Memory projection records not found")
    current_generation = max(row.generation for row in rows)
    if generation != current_generation:
        await session.commit()
        return {
            "message_id": message_id,
            "generation": current_generation,
            "reported_generation": generation,
            "status": "stale-report-ignored",
        }
    await require_work_lease(session, rows[0].task_id, body.get("work_lease_token"))

    by_projector = {row.projector: row for row in rows}
    normalized_reports: list[dict[str, Any]] = []
    for item in reports:
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail="Invalid projector report")
        projector = str(item.get("projector") or "")
        status_value = str(item.get("status") or "")
        if projector not in MEMORY_PROJECTORS or projector not in by_projector:
            raise HTTPException(status_code=422, detail=f"Unknown projector: {projector}")
        if status_value not in {"projected", "failed"}:
            raise HTTPException(status_code=422, detail=f"Invalid projection status: {status_value}")
        normalized_reports.append(
            {
                "projector": projector,
                "status": status_value,
                "projection_key": (
                    str(item["projection_key"])[:320] if item.get("projection_key") else None
                ),
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                "error": str(item.get("error") or "")[:4000] or None,
            }
        )

    already_applied = all(
        by_projector[item["projector"]].status == item["status"]
        and by_projector[item["projector"]].projection_key == item["projection_key"]
        and by_projector[item["projector"]].metadata_json == item["metadata"]
        and by_projector[item["projector"]].last_error == item["error"]
        for item in normalized_reports
    )
    if already_applied:
        failures = [item["projector"] for item in normalized_reports if item["status"] == "failed"]
        await session.commit()
        return {
            "message_id": message_id,
            "generation": generation,
            "status": "failed" if failures else "projected",
            "failed_projectors": failures,
            "idempotent_replay": True,
        }

    now = datetime.now(UTC)
    failures: list[str] = []
    for item in normalized_reports:
        row = by_projector[item["projector"]]
        row.status = item["status"]
        row.projection_key = item["projection_key"]
        row.metadata_json = item["metadata"]
        row.last_error = item["error"]
        row.projected_at = now if item["status"] == "projected" else None
        if item["status"] == "failed":
            failures.append(item["projector"])

    correlation_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"nevolium:memory-projection:{message_id}:v{MEMORY_SOURCE_VERSION}:g{generation}",
    )
    await enqueue_domain_event(
        session,
        event_type="memory.projection.failed" if failures else "memory.projection.completed",
        aggregate_type="conversation_message",
        aggregate_id=message_id,
        correlation_id=correlation_id,
        payload={
            "message_id": str(message_id),
            "generation": generation,
            "failed_projectors": failures,
        },
    )
    await append_audit(
        session,
        actor_type="worker",
        actor_id="memory-projector",
        action="memory.projection.report",
        resource_type="conversation_message",
        resource_id=str(message_id),
        authority_level=1,
        correlation_id=correlation_id,
        idempotency_key=f"memory:{message_id}:v{MEMORY_SOURCE_VERSION}:g{generation}:report",
        result_json={
            "generation": generation,
            "projectors": [
                {
                    "projector": item["projector"],
                    "status": item["status"],
                    "projection_key": item["projection_key"],
                }
                for item in normalized_reports
            ],
        },
    )
    await session.commit()
    return {
        "message_id": message_id,
        "generation": generation,
        "status": "failed" if failures else "projected",
        "failed_projectors": failures,
    }


@router.get("/v1/memory/projections/conversation-messages/{message_id}")
async def get_memory_projections(
    message_id: uuid.UUID,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _message, conversation = await _conversation_for_message(session, message_id)
    if conversation.subject_ref != principal.subject:
        raise HTTPException(status_code=404, detail="Conversation message not found")
    rows = await _projection_rows(session, message_id)
    return {
        "message_id": message_id,
        "projectors": [_projection_snapshot(row) for row in rows],
    }


class MemoryRebuildRequest(BaseModel):
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    message_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    cursor: str | None = Field(default=None, max_length=2048)
    through: str | None = Field(default=None, max_length=2048)
    limit: int = Field(default=100, ge=1, le=100)


def _rebuild_boundary(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created, identity = decode_cursor(cursor, 2)
        timestamp = datetime.fromisoformat(created)
        if timestamp.tzinfo is None:
            raise ValueError()
        return timestamp, uuid.UUID(identity)
    except (TypeError, ValueError, AttributeError, OverflowError) as exc:
        raise HTTPException(422, "Invalid rebuild cursor") from exc


@router.post("/internal/v1/memory/rebuild", dependencies=[Depends(require_operations_token)])
async def rebuild_memory_projections(
    body: MemoryRebuildRequest, session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    # One durable receipt per bounded page: retrying a lost response cannot advance generations twice.
    locked = await session.scalar(text("SELECT pg_try_advisory_xact_lock(1262572114, :key)"),
                                  {"key": 100 + body.request_id.int % 2000000000})
    if not locked:
        raise HTTPException(429, "Rebuild page is already being processed", headers={"Retry-After": "5"})
    receipt_id = uuid.uuid5(body.request_id, body.cursor or "first")
    request = body.model_dump(mode="json")
    receipt = await session.get(AuditRecord, receipt_id)
    if receipt:
        if receipt.request_json != request:
            raise HTTPException(409, "Rebuild request is already bound to different parameters")
        return receipt.result_json
    if body.cursor and not body.through:
        raise HTTPException(422, "Continuation requires the original through watermark")
    query = select(ConversationMessage)
    if body.message_ids is not None:
        query = query.where(ConversationMessage.id.in_(body.message_ids))
    through = body.through
    if through is None:
        last = await session.scalar(query.order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc()).limit(1))
        if last:
            through = encode_cursor([last.created_at, last.id])
    boundary = tuple_(ConversationMessage.created_at, ConversationMessage.id)
    if through:
        query = query.where(boundary <= _rebuild_boundary(through))
    if body.cursor:
        query = query.where(boundary > _rebuild_boundary(body.cursor))
    page = list((await session.execute(query.order_by(ConversationMessage.created_at, ConversationMessage.id)
                                      .limit(body.limit + 1))).scalars())
    messages = page[:body.limit]
    next_cursor = encode_cursor([messages[-1].created_at, messages[-1].id]) if len(page) > body.limit else None
    queued: list[dict[str, Any]] = []
    for message in messages:
        created = await _seed_projection_rows(session, message.id, 1)
        rows = await _projection_rows(session, message.id, lock=True)
        next_generation = max((row.generation for row in rows), default=0) + 1
        if created == len(MEMORY_PROJECTORS):
            next_generation = 1

        for row in rows:
            row.generation = next_generation
            row.status = "pending"
            row.task_id = None
            row.projection_key = None
            row.metadata_json = {}
            row.last_error = None
            row.projected_at = None

        correlation_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"nevolium:memory-rebuild:{message.id}:v{MEMORY_SOURCE_VERSION}:g{next_generation}",
        )
        await enqueue_domain_event(
            session,
            event_type="conversation.message.created",
            aggregate_type="conversation_message",
            aggregate_id=message.id,
            correlation_id=correlation_id,
            payload={
                "message_id": str(message.id),
                "conversation_id": str(message.conversation_id),
                "role": message.role,
                "projection_generation": next_generation,
                "reason": "memory.rebuild",
            },
        )
        queued.append({"message_id": str(message.id), "generation": next_generation})

    result = {"request_id": str(body.request_id), "queued": len(queued), "messages": queued,
              "next_cursor": next_cursor, "through": through, "complete": next_cursor is None}
    session.add(AuditRecord(
        id=receipt_id, actor_type="system", actor_id="memory-rebuilder", action="memory.rebuild.enqueue",
        resource_type="memory_projection", resource_id=str(body.request_id), authority_level=1,
        correlation_id=body.request_id, idempotency_key=f"memory-rebuild:{receipt_id}",
        request_json=request, result_json=result,
    ))
    await session.commit()
    return result
