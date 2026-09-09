from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .db import get_session
from .document_models import Document, DocumentChunk, DocumentVersion


router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])


class KnowledgeSearchHitRead(BaseModel):
    document_id: uuid.UUID
    document_title: str
    project_id: uuid.UUID
    media_type: str | None = None
    version_id: uuid.UUID
    generation: int
    chunk_id: uuid.UUID
    ordinal: int
    excerpt: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchRead(BaseModel):
    query: str
    results: list[KnowledgeSearchHitRead]


def _excerpt(text: str, query: str, *, radius: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= radius * 2:
        return compact
    index = compact.casefold().find(query.casefold())
    if index < 0:
        return compact[: radius * 2].rstrip() + "…"
    start = max(0, index - radius)
    end = min(len(compact), index + len(query) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(compact) else ""
    return prefix + compact[start:end].strip() + suffix


@router.get("/search", response_model=KnowledgeSearchRead)
async def search_knowledge(
    q: str = Query(min_length=2, max_length=240),
    limit: int = Query(default=24, ge=1, le=80),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeSearchRead:
    query = re.sub(r"\s+", " ", q).strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Knowledge query is too short")

    latest_completed = (
        select(
            DocumentVersion.document_id.label("document_id"),
            func.max(DocumentVersion.generation).label("generation"),
        )
        .where(DocumentVersion.status == "completed")
        .group_by(DocumentVersion.document_id)
        .subquery()
    )

    statement = (
        select(DocumentChunk, DocumentVersion, Document)
        .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
        .join(
            latest_completed,
            and_(
                latest_completed.c.document_id == DocumentVersion.document_id,
                latest_completed.c.generation == DocumentVersion.generation,
            ),
        )
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(Document.keycloak_subject == principal.subject)
        .where(DocumentChunk.text.ilike(f"%{query}%"))
        .order_by(Document.updated_at.desc(), DocumentChunk.ordinal.asc())
        .limit(limit)
    )
    rows = await session.execute(statement)

    results = [
        KnowledgeSearchHitRead(
            document_id=document.id,
            document_title=document.title,
            project_id=document.project_id,
            media_type=document.media_type,
            version_id=version.id,
            generation=version.generation,
            chunk_id=chunk.id,
            ordinal=chunk.ordinal,
            excerpt=_excerpt(chunk.text, query),
            metadata=dict(chunk.metadata_json or {}),
        )
        for chunk, version, document in rows
    ]
    return KnowledgeSearchRead(query=query, results=results)
