from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .db import get_session
from .ui_models import WorkspaceLayout

router = APIRouter()

MAX_WORKSPACE_LAYOUT_BYTES = 256_000
WORKSPACE_KEY_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,119}$"


class WorkspaceLayoutWrite(BaseModel):
    schema_version: int = Field(default=1, ge=1, le=10)
    layout: dict[str, Any] = Field(default_factory=dict)


class WorkspaceLayoutRead(BaseModel):
    id: uuid.UUID
    workspace_key: str
    schema_version: int
    layout: dict[str, Any]
    created_at: datetime
    updated_at: datetime


def _validate_layout_size(layout: dict[str, Any]) -> None:
    encoded = json.dumps(layout, ensure_ascii=False, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    if len(encoded) > MAX_WORKSPACE_LAYOUT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Workspace layout exceeds {MAX_WORKSPACE_LAYOUT_BYTES} bytes",
        )


def _read(row: WorkspaceLayout) -> WorkspaceLayoutRead:
    return WorkspaceLayoutRead(
        id=row.id,
        workspace_key=row.workspace_key,
        schema_version=row.schema_version,
        layout=row.layout_json or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/v1/ui/workspaces/{workspace_key}/layout", response_model=WorkspaceLayoutRead)
async def get_workspace_layout(
    workspace_key: str = Path(pattern=WORKSPACE_KEY_PATTERN),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceLayoutRead:
    row = await session.scalar(
        select(WorkspaceLayout).where(
            WorkspaceLayout.subject_ref == principal.subject,
            WorkspaceLayout.workspace_key == workspace_key,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace layout not found")
    return _read(row)


@router.put("/v1/ui/workspaces/{workspace_key}/layout", response_model=WorkspaceLayoutRead)
async def put_workspace_layout(
    body: WorkspaceLayoutWrite,
    workspace_key: str = Path(pattern=WORKSPACE_KEY_PATTERN),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceLayoutRead:
    _validate_layout_size(body.layout)
    statement = (
        pg_insert(WorkspaceLayout)
        .values(
            id=uuid.uuid4(),
            subject_ref=principal.subject,
            workspace_key=workspace_key,
            schema_version=body.schema_version,
            layout_json=body.layout,
        )
        .on_conflict_do_update(
            constraint="uq_workspace_layout_subject_key",
            set_={
                "schema_version": body.schema_version,
                "layout_json": body.layout,
            },
        )
        .returning(WorkspaceLayout)
    )
    row = (await session.execute(statement)).scalar_one()
    await session.commit()
    return _read(row)
