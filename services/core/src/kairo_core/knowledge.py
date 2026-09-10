from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from .auth import Principal, require_kairo_user
from .db import get_session
from .document_models import Document, DocumentChunk, DocumentVersion
from .project_access import get_owned_project

router = APIRouter()

MAX_KNOWLEDGE_SEARCH_RESULTS = 50
MAX_KNOWLEDGE_SEARCH_EXCERPT_CHARS = 1_000
MAX_KNOWLEDGE_CHUNK_WINDOW = 200


class KnowledgeSearchResultRead(BaseModel):
    document_id: uuid.UUID
    document_project_id: uuid.UUID
    document_title: str
    document_version_id: uuid.UUID
    generation: int
    chunk_id: uuid.UUID
    ordinal: int
    excerpt: str
    content_sha256: str
    rank: float = Field(ge=0)


class KnowledgeChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_version_id: uuid.UUID
    ordinal: int
    text: str
    content_sha256: str
    metadata_json: dict[str, object]
    created_at: datetime


class KnowledgeChunkWindowRead(BaseModel):
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    anchor_chunk_id: uuid.UUID
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
    chunks: list[KnowledgeChunkRead]


def _excerpt(text: str, query: str, limit: int = MAX_KNOWLEDGE_SEARCH_EXCERPT_CHARS) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value

    lowered = value.lower()
    terms = [
        match.group(0)
        for match in re.finditer(r"[\wÀ-ÖØ-öø-ÿ]{3,}", query.lower(), flags=re.UNICODE)
    ]
    positions = [lowered.find(term) for term in terms[:8]]
    positions = [position for position in positions if position >= 0]
    start = max(0, (min(positions) if positions else 0) - 240)
    end = min(len(value), start + limit)
    excerpt = value[start:end]
    if start > 0:
        excerpt = "…" + excerpt[1:]
    if end < len(value):
        excerpt = excerpt[:-1] + "…"
    return excerpt


@router.get("/v1/knowledge/search", response_model=list[KnowledgeSearchResultRead])
async def search_knowledge(
    project_id: uuid.UUID,
    q: str = Query(min_length=2, max_length=400),
    limit: int = Query(default=20, ge=1, le=MAX_KNOWLEDGE_SEARCH_RESULTS),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[KnowledgeSearchResultRead]:
    if not await get_owned_project(session, project_id, principal):
        raise HTTPException(status_code=404, detail="Project not found")

    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Knowledge search query is too short")

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

    rows = (
        await session.execute(
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
                Document.project_id == project_id,
                Document.status == "ready",
                Document.metadata_json["owner_subject"].astext == principal.subject,
                DocumentVersion.status == "completed",
                DocumentVersion.generation == latest_completed_generation,
                document_vector.op("@@")(query_vector),
            )
            .order_by(rank.desc(), Document.updated_at.desc(), DocumentChunk.ordinal)
            .limit(limit)
        )
    ).all()

    return [
        KnowledgeSearchResultRead(
            document_id=row[0],
            document_project_id=row[1],
            document_title=str(row[2]),
            document_version_id=row[3],
            generation=int(row[4]),
            chunk_id=row[5],
            ordinal=int(row[6]),
            excerpt=_excerpt(str(row[7]), query),
            content_sha256=str(row[8]),
            rank=max(0.0, float(row[9] or 0.0)),
        )
        for row in rows
    ]


@router.get("/v1/knowledge/chunk-window", response_model=KnowledgeChunkWindowRead)
async def get_knowledge_chunk_window(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    chunk_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=MAX_KNOWLEDGE_CHUNK_WINDOW),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeChunkWindowRead:
    if not await get_owned_project(session, project_id, principal):
        raise HTTPException(status_code=404, detail="Project not found")

    document = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
            Document.metadata_json["owner_subject"].astext == principal.subject,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    version = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document.id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Document version not found")

    anchor = await session.scalar(
        select(DocumentChunk).where(
            DocumentChunk.id == chunk_id,
            DocumentChunk.document_version_id == version.id,
        )
    )
    if anchor is None:
        raise HTTPException(status_code=404, detail="Document chunk not found")

    preceding = int(
        await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.document_version_id == version.id,
                DocumentChunk.ordinal < anchor.ordinal,
            )
        )
        or 0
    )
    offset = (preceding // limit) * limit

    chunks = list(
        (
            await session.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_version_id == version.id)
                .order_by(DocumentChunk.ordinal)
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
    )
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_version_id == version.id)
        )
        or 0
    )

    return KnowledgeChunkWindowRead(
        project_id=project_id,
        document_id=document.id,
        document_version_id=version.id,
        anchor_chunk_id=anchor.id,
        offset=offset,
        total=total,
        chunks=[KnowledgeChunkRead.model_validate(chunk) for chunk in chunks],
    )
