from __future__ import annotations

import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from .command_models import Conversation
from .config import settings
from .db import get_session
from .document_models import Document, DocumentChunk, DocumentVersion
from .models import Project, Task
from .security import require_internal_token

router = APIRouter()

DOCUMENT_CONTEXT_SOURCE = "postgresql-document-chunks"
MAX_DOCUMENT_CONTEXT_ITEMS = 12
MAX_DOCUMENT_CONTEXT_EXCERPT_CHARS = 2_000
MAX_GRAPHITI_CONVERSATION_GROUPS = 100


class CanonicalDocumentContextItem(BaseModel):
    context_id: str
    document_id: uuid.UUID
    document_project_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    generation: int
    ordinal: int
    excerpt: str
    content_sha256: str
    rank: float = Field(ge=0)


class ResearchDocumentContextRead(BaseModel):
    task_id: uuid.UUID
    query: str
    source: Literal["postgresql-document-chunks"] = DOCUMENT_CONTEXT_SOURCE
    items: list[CanonicalDocumentContextItem] = Field(default_factory=list)
    reason: str | None = None


class ResearchDerivedMemoryScopeRead(BaseModel):
    task_id: uuid.UUID
    query: str
    requester_subject: str | None = None
    mem0_user_id: str | None = None
    graphiti_group_ids: list[str] = Field(default_factory=list)
    graphiti_groups_truncated: bool = False
    reason: str | None = None


def _research_input(task: Task) -> dict:
    value = task.input or {}
    if str(value.get("capability") or "") != "research.autonomous":
        raise HTTPException(status_code=409, detail="Task is not an autonomous research task")
    return value


async def _require_research_task_owner_binding(
    task: Task,
    requester_subject: str,
    session: AsyncSession,
) -> None:
    project = await session.get(Project, task.project_id)
    if project is None:
        raise HTTPException(status_code=410, detail="Research project metadata is missing")
    if project.owner_subject == requester_subject:
        return
    if (
        not settings.nevolium_auth_enabled
        and project.owner_subject is None
        and requester_subject == "development-user"
    ):
        return
    raise HTTPException(status_code=409, detail="Research requester ownership binding is stale")


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for match in re.finditer(r"[\wÀ-ÖØ-öø-ÿ]{3,}", query.lower(), flags=re.UNICODE):
        term = match.group(0)
        if term not in terms:
            terms.append(term)
        if len(terms) >= 8:
            break
    return terms


def _excerpt(text: str, query: str, limit: int = MAX_DOCUMENT_CONTEXT_EXCERPT_CHARS) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value

    lowered = value.lower()
    positions = [lowered.find(term) for term in _query_terms(query)]
    positions = [position for position in positions if position >= 0]
    start = max(0, (min(positions) if positions else 0) - 240)
    end = min(len(value), start + limit)
    excerpt = value[start:end]
    if start > 0:
        excerpt = "…" + excerpt[1:]
    if end < len(value):
        excerpt = excerpt[:-1] + "…"
    return excerpt


def build_document_context_statement(*, requester_subject: str, query: str, limit: int):
    """Build the canonical latest-version, owner-scoped PostgreSQL full-text query."""

    latest = aliased(DocumentVersion)
    latest_completed_generation = (
        select(func.max(latest.generation))
        .where(
            latest.document_id == Document.id,
            latest.status == "completed",
        )
        .correlate(Document)
        .scalar_subquery()
    )

    searchable = func.concat(Document.title, " ", DocumentChunk.text)
    query_vector = func.plainto_tsquery("simple", query)
    document_vector = func.to_tsvector("simple", searchable)
    rank = func.ts_rank_cd(document_vector, query_vector)

    return (
        select(
            Document.id,
            Document.project_id,
            Document.title,
            DocumentVersion.id,
            DocumentVersion.generation,
            DocumentChunk.id,
            DocumentChunk.ordinal,
            DocumentChunk.text,
            DocumentChunk.content_sha256,
            rank.label("rank"),
        )
        .join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .join(DocumentChunk, DocumentChunk.document_version_id == DocumentVersion.id)
        .where(
            Document.status == "ready",
            DocumentVersion.status == "completed",
            DocumentVersion.generation == latest_completed_generation,
            Document.metadata_json["owner_subject"].astext == requester_subject,
            document_vector.op("@@")(query_vector),
        )
        .order_by(rank.desc(), Document.updated_at.desc(), DocumentChunk.ordinal)
        .limit(max(1, min(MAX_DOCUMENT_CONTEXT_ITEMS, int(limit))))
    )


def build_graphiti_scope_statement(*, requester_subject: str):
    """Return recent canonical conversation ids that authorize Graphiti group access."""

    return (
        select(Conversation.id)
        .where(Conversation.subject_ref == requester_subject)
        .order_by(Conversation.updated_at.desc(), Conversation.id)
        .limit(MAX_GRAPHITI_CONVERSATION_GROUPS + 1)
    )


@router.get(
    "/internal/v1/research/tasks/{task_id}/document-context",
    response_model=ResearchDocumentContextRead,
    dependencies=[Depends(require_internal_token)],
)
async def get_research_document_context(
    task_id: uuid.UUID,
    limit: int = Query(default=6, ge=1, le=MAX_DOCUMENT_CONTEXT_ITEMS),
    session: AsyncSession = Depends(get_session),
) -> ResearchDocumentContextRead:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Research task not found")
    task_input = _research_input(task)
    query = str(task_input.get("query") or "").strip()
    requester_subject = str(task_input.get("requester_subject") or "").strip()

    if not requester_subject:
        return ResearchDocumentContextRead(
            task_id=task.id,
            query=query,
            items=[],
            reason="requester_subject_unavailable",
        )
    if not query:
        return ResearchDocumentContextRead(
            task_id=task.id,
            query=query,
            items=[],
            reason="query_unavailable",
        )

    await _require_research_task_owner_binding(task, requester_subject, session)
    statement = build_document_context_statement(
        requester_subject=requester_subject,
        query=query,
        limit=limit,
    )
    rows = (await session.execute(statement)).all()

    items = [
        CanonicalDocumentContextItem(
            context_id=f"D{position}",
            document_id=row[0],
            document_project_id=row[1],
            title=str(row[2]),
            document_version_id=row[3],
            generation=int(row[4]),
            chunk_id=row[5],
            ordinal=int(row[6]),
            excerpt=_excerpt(str(row[7]), query),
            content_sha256=str(row[8]),
            rank=max(0.0, float(row[9] or 0.0)),
        )
        for position, row in enumerate(rows, start=1)
    ]
    return ResearchDocumentContextRead(
        task_id=task.id,
        query=query,
        items=items,
        reason=None if items else "no_matching_canonical_document_chunks",
    )


@router.get(
    "/internal/v1/research/tasks/{task_id}/derived-memory-scope",
    response_model=ResearchDerivedMemoryScopeRead,
    dependencies=[Depends(require_internal_token)],
)
async def get_research_derived_memory_scope(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ResearchDerivedMemoryScopeRead:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Research task not found")
    task_input = _research_input(task)
    query = str(task_input.get("query") or "").strip()
    requester_subject = str(task_input.get("requester_subject") or "").strip()
    if not requester_subject:
        return ResearchDerivedMemoryScopeRead(
            task_id=task.id,
            query=query,
            reason="requester_subject_unavailable",
        )

    await _require_research_task_owner_binding(task, requester_subject, session)
    rows = (
        await session.execute(build_graphiti_scope_statement(requester_subject=requester_subject))
    ).scalars().all()
    truncated = len(rows) > MAX_GRAPHITI_CONVERSATION_GROUPS
    visible = rows[:MAX_GRAPHITI_CONVERSATION_GROUPS]
    return ResearchDerivedMemoryScopeRead(
        task_id=task.id,
        query=query,
        requester_subject=requester_subject,
        mem0_user_id=f"subject:{requester_subject}",
        graphiti_group_ids=[f"conversation:{conversation_id}" for conversation_id in visible],
        graphiti_groups_truncated=truncated,
        reason=None,
    )
