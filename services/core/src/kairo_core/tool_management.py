from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_admin
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .tool_models import ToolDefinition, ToolServer
from .tools import ToolServerRead


router = APIRouter(tags=["tools"])


class ToolServerPolicyUpdate(BaseModel):
    enabled: bool


@router.patch("/v1/tool-servers/{server_key}/policy", response_model=ToolServerRead)
async def update_tool_server_policy(
    server_key: str,
    body: ToolServerPolicyUpdate,
    principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> ToolServer:
    server = await session.scalar(
        select(ToolServer).where(ToolServer.key == server_key).with_for_update()
    )
    if server is None:
        raise HTTPException(status_code=404, detail="Tool server not found")

    changed = server.enabled != body.enabled
    server.enabled = body.enabled
    disabled_tools: list[str] = []
    if not body.enabled:
        rows = await session.execute(
            select(ToolDefinition).where(ToolDefinition.server_id == server.id)
        )
        for tool in rows.scalars():
            if tool.enabled:
                tool.enabled = False
                disabled_tools.append(tool.key)

    if changed or disabled_tools:
        correlation_id = uuid.uuid4()
        await enqueue_domain_event(
            session,
            event_type="tool.server.policy.updated",
            aggregate_type="tool_server",
            aggregate_id=server.id,
            correlation_id=correlation_id,
            payload={
                "tool_server_id": str(server.id),
                "key": server.key,
                "enabled": server.enabled,
                "disabled_tools": disabled_tools,
            },
        )
        await append_audit(
            session,
            actor_type="user",
            actor_id=principal.subject,
            action="tool.server.policy.update",
            resource_type="tool_server",
            resource_id=str(server.id),
            authority_level=2,
            correlation_id=correlation_id,
            request_json={"enabled": body.enabled},
            result_json={"disabled_tools": disabled_tools},
        )

    await session.commit()
    await session.refresh(server)
    return server
