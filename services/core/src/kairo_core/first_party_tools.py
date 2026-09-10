from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .security import require_internal_token
from .tool_models import ToolDefinition, ToolServer
from .tools import ToolCatalogSync, ToolDefinitionRead, sync_tool_catalog

router = APIRouter()

WEB_SERVER_KEY = "kairo-web"
WEB_NAMESPACE = "web"
WEB_TOOL_KEY = "web.search"


class FirstPartyWebBootstrapRead(BaseModel):
    server_id: uuid.UUID
    server_enabled: bool
    tool: ToolDefinitionRead
    initial_activation: bool


def _validate_web_catalog(body: ToolCatalogSync) -> None:
    if len(body.tools) != 1 or body.tools[0].name != "search":
        raise HTTPException(
            status_code=422,
            detail="The first-party Web MCP adapter must expose exactly the search tool",
        )
    annotations = body.tools[0].annotations
    if annotations.get("readOnlyHint") is not True or annotations.get("destructiveHint") is True:
        raise HTTPException(
            status_code=422,
            detail="The first-party Web MCP search tool must declare itself read-only",
        )


@router.post(
    "/internal/v1/system-tools/web/catalog",
    response_model=FirstPartyWebBootstrapRead,
    dependencies=[Depends(require_internal_token)],
)
async def bootstrap_web_tool_catalog(
    body: ToolCatalogSync,
    session: AsyncSession = Depends(get_session),
) -> FirstPartyWebBootstrapRead:
    """Idempotently bind KAIRO's own Web MCP adapter to the canonical tool registry.

    Core owns the server identity and the first activation policy. An unchanged resync preserves
    administrator policy. Schema drift is deliberately *not* auto-enabled: the normal catalog sync
    disables the definition and this bootstrap leaves it disabled for explicit review.
    """

    _validate_web_catalog(body)
    server = await session.scalar(
        select(ToolServer)
        .where(or_(ToolServer.key == WEB_SERVER_KEY, ToolServer.namespace == WEB_NAMESPACE))
        .with_for_update()
    )
    created_server = server is None
    if server is None:
        server = ToolServer(
            key=WEB_SERVER_KEY,
            namespace=WEB_NAMESPACE,
            title="KAIRO Web Research",
            transport="mcp_streamable_http",
            endpoint_url=settings.kairo_web_mcp_url,
            enabled=True,
            metadata_json={"first_party": True, "managed_by": "kairo-core"},
        )
        session.add(server)
        await session.flush()
        correlation_id = uuid.uuid4()
        await enqueue_domain_event(
            session,
            event_type="tool.server.created",
            aggregate_type="tool_server",
            aggregate_id=server.id,
            correlation_id=correlation_id,
            payload={
                "tool_server_id": str(server.id),
                "key": server.key,
                "namespace": server.namespace,
                "first_party": True,
            },
        )
        await append_audit(
            session,
            actor_type="core",
            actor_id="first-party-tool-bootstrap",
            action="tool.server.bootstrap",
            resource_type="tool_server",
            resource_id=str(server.id),
            authority_level=2,
            correlation_id=correlation_id,
            request_json={"key": WEB_SERVER_KEY, "namespace": WEB_NAMESPACE},
        )
        await session.commit()
        await session.refresh(server)
    elif server.key != WEB_SERVER_KEY or server.namespace != WEB_NAMESPACE:
        raise HTTPException(
            status_code=409,
            detail="Web tool server key/namespace is already bound inconsistently",
        )
    else:
        # Endpoint/title are KAIRO-owned deployment metadata. Do not silently re-enable a server an
        # administrator intentionally disabled.
        changed = False
        if server.endpoint_url != settings.kairo_web_mcp_url:
            server.endpoint_url = settings.kairo_web_mcp_url
            changed = True
        if server.title != "KAIRO Web Research":
            server.title = "KAIRO Web Research"
            changed = True
        metadata = {**(server.metadata_json or {}), "first_party": True, "managed_by": "kairo-core"}
        if metadata != (server.metadata_json or {}):
            server.metadata_json = metadata
            changed = True
        if changed:
            await session.commit()
            await session.refresh(server)

    existing = await session.scalar(
        select(ToolDefinition).where(
            ToolDefinition.server_id == server.id,
            ToolDefinition.remote_name == "search",
        )
    )
    first_definition = existing is None

    definitions = await sync_tool_catalog(server.id, body, session)
    tool = next((item for item in definitions if item.key == WEB_TOOL_KEY), None)
    if tool is None:
        raise HTTPException(status_code=409, detail="Web search definition was not synchronized")

    initial_activation = False
    if first_definition:
        # The initial policy is a KAIRO-owned constant, not a remote MCP annotation. Later manual
        # disables or schema-drift disables remain authoritative and are never undone here.
        tool.enabled = True
        tool.authority_level = 1
        tool.estimated_cost_usd = Decimal("0")
        tool.risk_class = "read"
        tool.retry_policy = "safe_retry"
        correlation_id = uuid.uuid4()
        await enqueue_domain_event(
            session,
            event_type="tool.policy.updated",
            aggregate_type="tool_definition",
            aggregate_id=tool.id,
            correlation_id=correlation_id,
            payload={
                "tool_key": tool.key,
                "enabled": "True",
                "authority_level": "1",
                "estimated_cost_usd": "0",
                "risk_class": "read",
                "retry_policy": "safe_retry",
                "source": "first-party-initial-policy",
            },
        )
        await append_audit(
            session,
            actor_type="core",
            actor_id="first-party-tool-bootstrap",
            action="tool.policy.bootstrap",
            resource_type="tool_definition",
            resource_id=str(tool.id),
            authority_level=1,
            correlation_id=correlation_id,
            request_json={"tool_key": WEB_TOOL_KEY, "first_party": True},
        )
        await session.commit()
        await session.refresh(tool)
        initial_activation = True

    return FirstPartyWebBootstrapRead(
        server_id=server.id,
        server_enabled=server.enabled,
        tool=ToolDefinitionRead.model_validate(tool),
        initial_activation=initial_activation,
    )
