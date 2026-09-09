from __future__ import annotations

import hashlib
import re
import uuid
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .config import settings
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Asset
from .ownership import require_owned_project
from .schemas import AssetRead

router = APIRouter()


def _safe_filename(value: str | None) -> str:
    candidate = (value or "asset.bin").strip()
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip(".-")
    return (candidate or "asset.bin")[:180]


def _filer_url(object_key: str) -> str:
    return f"{settings.seaweed_filer_endpoint.rstrip('/')}/{quote(object_key, safe='/')}"


def _owned(asset: Asset, principal: Principal) -> bool:
    return str((asset.metadata_json or {}).get("owner_subject") or "") == principal.subject


async def _get_owned_asset(
    asset_id: uuid.UUID, principal: Principal, session: AsyncSession
) -> Asset:
    asset = await session.get(Asset, asset_id)
    if not asset or not _owned(asset, principal):
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.post("/v1/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    project_id: uuid.UUID | None = Form(default=None),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Asset:
    if project_id is not None:
        await require_owned_project(session, project_id, principal.subject)

    content = await file.read(settings.asset_max_bytes + 1)
    if len(content) > settings.asset_max_bytes:
        raise HTTPException(status_code=413, detail="Asset exceeds configured size limit")

    filename = _safe_filename(file.filename)
    scope = str(project_id) if project_id else "unscoped"
    object_key = f"kairo/assets/{scope}/{uuid.uuid4()}/{filename}"
    mime_type = file.content_type or "application/octet-stream"
    digest = hashlib.sha256(content).hexdigest()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _filer_url(object_key),
                files={"file": (filename, content, mime_type)},
            )
        response.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SeaweedFS filer is unavailable",
        ) from exc

    correlation_id = uuid.uuid4()
    asset = Asset(
        project_id=project_id,
        bucket="kairo",
        object_key=object_key,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=digest,
        metadata_json={"filename": filename, "owner_subject": principal.subject},
    )
    session.add(asset)
    try:
        await session.flush()
        await enqueue_domain_event(
            session,
            event_type="asset.created",
            aggregate_type="asset",
            aggregate_id=asset.id,
            correlation_id=correlation_id,
            payload={
                "asset_id": str(asset.id),
                "project_id": str(project_id) if project_id else None,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "sha256": digest,
            },
        )
        await append_audit(
            session,
            actor_type="user",
            actor_id=principal.subject,
            action="asset.upload",
            resource_type="asset",
            resource_id=str(asset.id),
            authority_level=1,
            correlation_id=correlation_id,
            request_json={
                "project_id": str(project_id) if project_id else None,
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "sha256": digest,
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(_filer_url(object_key))
        finally:
            raise

    await session.refresh(asset)
    return asset


@router.get("/v1/assets", response_model=list[AssetRead])
async def list_assets(
    project_id: uuid.UUID | None = None,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[Asset]:
    if project_id is not None:
        await require_owned_project(session, project_id, principal.subject)
    statement = select(Asset).order_by(Asset.created_at)
    if project_id is not None:
        statement = statement.where(Asset.project_id == project_id)
    result = await session.execute(statement)
    return [asset for asset in result.scalars() if _owned(asset, principal)]


@router.get("/v1/assets/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Asset:
    return await _get_owned_asset(asset_id, principal, session)


@router.get("/v1/assets/{asset_id}/content")
async def get_asset_content(
    asset_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    asset = await _get_owned_asset(asset_id, principal, session)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_filer_url(asset.object_key))
        if response.status_code == 404:
            raise HTTPException(status_code=410, detail="Asset object is missing from SeaweedFS")
        response.raise_for_status()
    except HTTPException:
        raise
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SeaweedFS filer is unavailable",
        ) from exc

    filename = _safe_filename((asset.metadata_json or {}).get("filename"))
    return Response(
        content=response.content,
        media_type=asset.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Content-SHA256": asset.sha256 or "",
        },
    )


@router.delete("/v1/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    asset = await _get_owned_asset(asset_id, principal, session)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.delete(_filer_url(asset.object_key))
        if response.status_code not in {200, 202, 204, 404}:
            response.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SeaweedFS filer is unavailable; canonical metadata was preserved",
        ) from exc

    correlation_id = uuid.uuid4()
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="asset.delete",
        resource_type="asset",
        resource_id=str(asset.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"object_key": asset.object_key, "sha256": asset.sha256},
    )
    await session.delete(asset)
    await session.commit()
