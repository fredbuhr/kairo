from __future__ import annotations

import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from .db import get_session
from .document_models import Document, DocumentChunk, DocumentVersion
from .models import Task
from .security import require_internal_token

router = APIRouter()

DOCUMENT_CONTEXT_SOURCE = "postgresql-document-chunks"
MAX_DOCUMENT_CONTEXT_ITEMS = 12
MAX_DOCUMENT_CONTEXT_EXCERPT_CHARS = 2_000


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


def _research_input(task: Task) -> dict:
    value = task.input or {}
    if str(value.get("capability") or "") != "research.autonomous":
        raise HTTPException(status_code=409, detail="Task is not an autonomous research task")
    return value


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

    statement = (
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
        .limit(limit)
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
