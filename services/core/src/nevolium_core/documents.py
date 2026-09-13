from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_nevolium_user
from .config import settings
from .pagination import PageCursor, PageLimit, page_rows
from fastapi import Response
from .db import get_session
from .work_capacity import ensure_work_request, require_work_lease
from .document_models import DOCUMENTS_PROJECT_ID, Document, DocumentChunk, DocumentVersion
from .events import append_audit, enqueue_domain_event
from .models import Asset, Project, Task
from .project_access import get_owned_project
from .security import require_internal_token
from .workflows import run_task

router = APIRouter()


class DocumentCreate(BaseModel):
    asset_id: uuid.UUID
    title: str | None = Field(default=None, max_length=320)


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_version_id: uuid.UUID
    ordinal: int
    text: str
    content_sha256: str
    metadata_json: dict[str, Any]
    created_at: datetime


class DocumentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    generation: int
    task_id: uuid.UUID | None
    parser: str
    parser_version: str | None
    source_sha256: str | None
    status: str
    chunk_count: int
    metadata_json: dict[str, Any]
    last_error: str | None
    created_at: datetime
    completed_at: datetime | None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    media_type: str | None
    source_sha256: str | None
    status: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DocumentRunResponse(BaseModel):
    document: DocumentRead
    version: DocumentVersionRead
    workflow_execution_id: uuid.UUID
    workflow_id: str
    workflow_status: str


class InternalDocumentProjectionReport(BaseModel):
    parser: str = Field(min_length=1, max_length=120)
    parser_version: str | None = Field(default=None, max_length=80)
    source_sha256: str = Field(min_length=64, max_length=64)
    chunks: list[dict[str, Any]] = Field(default_factory=list, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _owned_asset(asset: Asset, principal: Principal) -> bool:
    return str((asset.metadata_json or {}).get("owner_subject") or "") == principal.subject


def _filer_url(object_key: str) -> str:
    return f"{settings.seaweed_filer_endpoint.rstrip('/')}/{quote(object_key, safe='/')}"


def _task_id(version_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"nevolium:document-ingest:{version_id}")


def _chunk_id(version_id: uuid.UUID, ordinal: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"nevolium:document-chunk:{version_id}:{ordinal}")


def _documents_project_id(subject: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"nevolium:project:documents:subject:{subject}")


async def _ensure_documents_project(session: AsyncSession, subject: str) -> Project:
    normalized_subject = subject.strip()
    if not normalized_subject:
        raise HTTPException(status_code=409, detail="Document owner is missing")

    project_id = _documents_project_id(normalized_subject)
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_subject == normalized_subject,
        )
    )
    if project is not None:
        return project

    correlation_id = uuid.uuid4()
    inserted_id = await session.scalar(
        pg_insert(Project)
        .values(
            id=project_id,
            owner_subject=normalized_subject,
            name="Nevolium Documents",
            status="active",
            summary=(
                "Per-user system workspace for canonical documents imported without an explicit Project."
            ),
            parent_id=None,
        )
        .on_conflict_do_nothing(index_elements=[Project.id])
        .returning(Project.id)
    )
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_subject == normalized_subject,
        )
    )
    if project is None:
        raise RuntimeError("Nevolium Documents workspace could not be initialized for this owner")

    if inserted_id is not None:
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
            actor_id="document-ingestion",
            action="project.create",
            resource_type="project",
            resource_id=str(project.id),
            authority_level=0,
            correlation_id=correlation_id,
            request_json={
                "reason": "initialize owner-scoped Documents workspace",
                "subject": normalized_subject,
            },
        )
    return project


async def _project_for_asset(
    asset: Asset,
    principal: Principal,
    session: AsyncSession,
) -> Project:
    if asset.project_id is None:
        return await _ensure_documents_project(session, principal.subject)

    project = await get_owned_project(session, asset.project_id, principal)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _repair_reingest_project(
    document: Document,
    asset: Asset,
    principal: Principal,
    session: AsyncSession,
) -> None:
    current_project = await get_owned_project(session, document.project_id, principal)
    if current_project is not None and document.project_id != DOCUMENTS_PROJECT_ID:
        return

    project = await _project_for_asset(asset, principal, session)
    document.project_id = project.id


async def _require_internal_source_binding(
    version: DocumentVersion,
    document: Document,
    asset: Asset,
    session: AsyncSession,
) -> None:
    document_subject = str((document.metadata_json or {}).get("owner_subject") or "").strip()
    asset_subject = str((asset.metadata_json or {}).get("owner_subject") or "").strip()
    if not document_subject or asset_subject != document_subject:
        raise HTTPException(status_code=409, detail="Document source ownership binding is stale")

    project = await session.get(Project, document.project_id)
    if project is None:
        raise HTTPException(status_code=410, detail="Document project metadata is missing")
    if project.owner_subject != document_subject:
        if settings.nevolium_auth_enabled or project.owner_subject is not None:
            raise HTTPException(status_code=409, detail="Document project ownership binding is stale")

    if asset.project_id is not None and asset.project_id != document.project_id:
        raise HTTPException(status_code=409, detail="Document source project binding is stale")

    if version.task_id is None:
        raise HTTPException(status_code=409, detail="Document version has no ingestion task binding")
    task = await session.get(Task, version.task_id)
    if task is None:
        raise HTTPException(status_code=410, detail="Document ingestion task metadata is missing")

    task_input = task.input or {}
    expected_input = {
        "capability": "document.ingest",
        "document_id": str(document.id),
        "document_version_id": str(version.id),
        "asset_id": str(asset.id),
    }
    actual_input = {key: str(task_input.get(key) or "") for key in expected_input}
    if (
        task.project_id != document.project_id
        or task.owner_type != "user"
        or str(task.owner_ref or "") != document_subject
        or actual_input != expected_input
    ):
        raise HTTPException(status_code=409, detail="Document version ingestion binding is stale")


async def _start_version(
    document: Document,
    asset: Asset,
    generation: int,
    session: AsyncSession,
    *,
    actor_id: str,
) -> tuple[DocumentVersion, Any]:
    correlation_id = uuid.uuid4()
    version = DocumentVersion(
        document_id=document.id,
        generation=generation,
        parser="docling",
        source_sha256=asset.sha256,
        status="queued",
        metadata_json={"asset_id": str(asset.id), "media_type": asset.mime_type},
    )
    session.add(version)
    await session.flush()

    task = Task(
        id=_task_id(version.id),
        project_id=document.project_id,
        title=f"Ingest document — {document.title}"[:320],
        description="Parse a canonical Nevolium Asset into versioned document chunks.",
        status="todo",
        owner_type="user",
        owner_ref=actor_id,
        authority_ceiling=1,
        budget_usd=0,
        input={
            "capability": "document.ingest",
            "authority_level": 1,
            "estimated_cost_usd": "0",
            "document_id": str(document.id),
            "document_version_id": str(version.id),
            "asset_id": str(asset.id),
            "generation": generation,
        },
    )
    session.add(task)
    await session.flush()
    version.task_id = task.id
    document.status = "processing"
    await ensure_work_request(session, task)

    await enqueue_domain_event(
        session,
        event_type="document.ingestion.requested",
        aggregate_type="document_version",
        aggregate_id=version.id,
        correlation_id=correlation_id,
        payload={
            "document_id": str(document.id),
            "document_version_id": str(version.id),
            "asset_id": str(asset.id),
            "generation": generation,
            "source_sha256": asset.sha256,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=actor_id,
        action="document.ingest.request",
        resource_type="document",
        resource_id=str(document.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "asset_id": str(asset.id),
            "document_version_id": str(version.id),
            "generation": generation,
        },
    )
    await session.commit()
    run = await run_task(task.id, session)
    await session.refresh(version)
    await session.refresh(document)
    return version, run


@router.post("/v1/documents", response_model=DocumentRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_document(
    body: DocumentCreate,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentRunResponse:
    asset = await session.get(Asset, body.asset_id)
    if not asset or not _owned_asset(asset, principal):
        raise HTTPException(status_code=404, detail="Asset not found")
    existing = await session.scalar(select(Document).where(Document.asset_id == asset.id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Asset is already bound to a document")

    project = await _project_for_asset(asset, principal, session)
    title = (body.title or (asset.metadata_json or {}).get("filename") or "Document").strip()
    document = Document(
        asset_id=asset.id,
        project_id=project.id,
        title=title[:320],
        media_type=asset.mime_type,
        source_sha256=asset.sha256,
        status="pending",
        metadata_json={"owner_subject": principal.subject},
    )
    session.add(document)
    await session.flush()
    version, run = await _start_version(document, asset, 1, session, actor_id=principal.subject)
    return DocumentRunResponse(
        document=document,
        version=version,
        workflow_execution_id=run.workflow_execution_id,
        workflow_id=run.workflow_id,
        workflow_status=run.status,
    )


@router.post(
    "/v1/documents/{document_id}/reingest",
    response_model=DocumentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reingest_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentRunResponse:
    document = await session.get(Document, document_id)
    if not document or str((document.metadata_json or {}).get("owner_subject") or "") != principal.subject:
        raise HTTPException(status_code=404, detail="Document not found")
    asset = await session.get(Asset, document.asset_id)
    if asset is None:
        raise HTTPException(status_code=410, detail="Source asset metadata is missing")
    if not _owned_asset(asset, principal):
        raise HTTPException(status_code=409, detail="Document source ownership binding is stale")

    await _repair_reingest_project(document, asset, principal, session)
    generation = int(
        (
            await session.scalar(
                select(func.max(DocumentVersion.generation)).where(
                    DocumentVersion.document_id == document.id
                )
            )
        )
        or 0
    ) + 1
    version, run = await _start_version(
        document,
        asset,
        generation,
        session,
        actor_id=principal.subject,
    )
    return DocumentRunResponse(
        document=document,
        version=version,
        workflow_execution_id=run.workflow_execution_id,
        workflow_id=run.workflow_id,
        workflow_status=run.status,
    )


@router.get("/v1/documents", response_model=list[DocumentRead])
async def list_documents(
    project_id: uuid.UUID | None = None,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
    response: Response = None,
    limit: PageLimit = 100,
    cursor: PageCursor = None,
) -> list[Document]:
    statement = select(Document).where(Document.metadata_json["owner_subject"].astext == principal.subject)
    if project_id is not None:
        statement = statement.where(Document.project_id == project_id)
    return await page_rows(session, statement, Document, limit=limit, cursor=cursor,
                           response=response, descending=True)


@router.get("/v1/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> Document:
    document = await session.get(Document, document_id)
    if not document or str((document.metadata_json or {}).get("owner_subject") or "") != principal.subject:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/v1/documents/{document_id}/versions", response_model=list[DocumentVersionRead])
async def list_document_versions(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
    response: Response = None,
    limit: PageLimit = 100,
    cursor: PageCursor = None,
) -> list[DocumentVersion]:
    await get_document(document_id, principal, session)
    return await page_rows(session, select(DocumentVersion).where(DocumentVersion.document_id == document_id),
                           DocumentVersion, limit=limit, cursor=cursor, response=response,
                           descending=True, key_name="generation")


@router.get("/v1/document-versions/{version_id}", response_model=DocumentVersionRead)
async def get_document_version(version_id: uuid.UUID, principal: Principal = Depends(require_nevolium_user),
                               session: AsyncSession = Depends(get_session)) -> DocumentVersion:
    version = await session.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(404, "Document version not found")
    await get_document(version.document_id, principal, session)
    return version


@router.get("/v1/document-versions/{version_id}/chunks", response_model=list[DocumentChunkRead])
async def list_document_chunks(
    version_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentChunk]:
    version = await session.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    await get_document(version.document_id, principal, session)
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_version_id == version.id)
        .order_by(DocumentChunk.ordinal)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars())


@router.get(
    "/internal/v1/documents/versions/{version_id}/source",
    dependencies=[Depends(require_internal_token)],
)
async def internal_document_source(
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    version = await session.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    document = await session.get(Document, version.document_id)
    asset = await session.get(Asset, document.asset_id) if document else None
    if document is None or asset is None:
        raise HTTPException(status_code=410, detail="Document source asset is unavailable")

    await _require_internal_source_binding(version, document, asset, session)
    return {
        "document_id": str(document.id),
        "document_version_id": str(version.id),
        "generation": version.generation,
        "title": document.title,
        "media_type": asset.mime_type,
        "filename": (asset.metadata_json or {}).get("filename"),
        "size_bytes": asset.size_bytes,
        "source_sha256": asset.sha256,
        "download_url": _filer_url(asset.object_key),
    }


@router.post(
    "/internal/v1/documents/versions/{version_id}/complete",
    dependencies=[Depends(require_internal_token)],
)
async def internal_complete_document_ingestion(
    version_id: uuid.UUID,
    body: InternalDocumentProjectionReport,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    version = await session.get(DocumentVersion, version_id, with_for_update=True)
    if version is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    document = await session.get(Document, version.document_id, with_for_update=True)
    if document is None:
        raise HTTPException(status_code=410, detail="Document is missing")
    asset = await session.get(Asset, document.asset_id)
    if asset is None:
        raise HTTPException(status_code=410, detail="Document source asset is unavailable")

    await _require_internal_source_binding(version, document, asset, session)
    await require_work_lease(session, version.task_id, body.metadata.get("work_lease_token"))
    if version.source_sha256 and body.source_sha256 != version.source_sha256:
        raise HTTPException(status_code=409, detail="Document source digest changed during ingestion")

    await session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_version_id == version.id)
    )
    for ordinal, item in enumerate(body.chunks):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        session.add(
            DocumentChunk(
                id=_chunk_id(version.id, ordinal),
                document_version_id=version.id,
                ordinal=ordinal,
                text=text,
                content_sha256=digest,
                metadata_json=dict(item.get("metadata") or {}),
            )
        )

    await session.flush()
    count = int(
        await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_version_id == version.id)
        )
        or 0
    )
    version.parser = body.parser
    version.parser_version = body.parser_version
    version.chunk_count = count
    version.status = "completed"
    version.last_error = None
    version.completed_at = datetime.now(UTC)
    version.metadata_json = {**(version.metadata_json or {}), **{key: value for key, value in body.metadata.items() if key != "work_lease_token"}}
    document.status = "ready"

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="document.ingestion.completed",
        aggregate_type="document_version",
        aggregate_id=version.id,
        correlation_id=correlation_id,
        payload={
            "document_id": str(document.id),
            "document_version_id": str(version.id),
            "generation": version.generation,
            "chunk_count": count,
            "parser": body.parser,
        },
    )
    await append_audit(
        session,
        actor_type="system",
        actor_id="document-ingestion",
        action="document.ingest.complete",
        resource_type="document_version",
        resource_id=str(version.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "chunk_count": count,
            "parser": body.parser,
            "parser_version": body.parser_version,
        },
    )
    await session.commit()
    return {
        "document_id": str(document.id),
        "version_id": str(version.id),
        "status": version.status,
        "chunk_count": count,
    }


@router.post(
    "/internal/v1/documents/versions/{version_id}/fail",
    dependencies=[Depends(require_internal_token)],
)
async def internal_fail_document_ingestion(
    version_id: uuid.UUID,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    version = await session.get(DocumentVersion, version_id, with_for_update=True)
    if version is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    document = await session.get(Document, version.document_id, with_for_update=True)
    if document is None:
        raise HTTPException(status_code=410, detail="Document is missing")
    asset = await session.get(Asset, document.asset_id)
    if asset is None:
        raise HTTPException(status_code=410, detail="Document source asset is unavailable")

    await _require_internal_source_binding(version, document, asset, session)
    await require_work_lease(session, version.task_id, body.get("work_lease_token"))
    version.status = "failed"
    version.last_error = str(body.get("error") or "Document ingestion failed")[:4000]
    version.completed_at = datetime.now(UTC)
    document.status = "failed"
    await session.commit()
    return {"version_id": str(version.id), "status": version.status}
