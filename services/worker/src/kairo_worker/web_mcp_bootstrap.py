from __future__ import annotations

import asyncio
import os
import urllib.parse
from typing import Any

import httpx
from mcp import Client

from .config import settings

WEB_SERVER_KEY = "kairo-web"
WEB_NAMESPACE = "web"
WEB_TITLE = "KAIRO Web Research"
DEFAULT_WEB_MCP_URL = "http://kairo-web-mcp:8090/mcp"
EXPECTED_TOOL_NAMES = {"search", "fetch"}


def _admin_headers() -> dict[str, str]:
    token = os.getenv("KAIRO_ADMIN_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _internal_headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _annotations(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("annotations") if isinstance(payload.get("annotations"), dict) else {}
    read_only = bool(raw.get("readOnlyHint", raw.get("read_only_hint", False)))
    destructive = bool(raw.get("destructiveHint", raw.get("destructive_hint", False)))
    return {
        "readOnlyHint": read_only,
        # MCP defines destructiveHint only for non-read-only tools. Normalize it away when the
        # first-party server declares the stronger read-only contract.
        "destructiveHint": False if read_only else destructive,
        "idempotentHint": bool(raw.get("idempotentHint", raw.get("idempotent_hint", False))),
        "openWorldHint": bool(raw.get("openWorldHint", raw.get("open_world_hint", True))),
    }


def catalog_item(tool: Any) -> dict[str, Any]:
    dumped = tool.model_dump(mode="json", by_alias=True)
    annotations = _annotations(dumped)
    if not annotations["readOnlyHint"]:
        raise RuntimeError(f"First-party Web MCP tool {dumped.get('name')} is not declared read-only")
    input_schema = dumped.get("inputSchema", dumped.get("input_schema"))
    output_schema = dumped.get("outputSchema", dumped.get("output_schema"))
    return {
        "name": str(dumped.get("name") or ""),
        "title": dumped.get("title"),
        "description": dumped.get("description"),
        "input_schema": input_schema if isinstance(input_schema, dict) else {},
        "output_schema": output_schema if isinstance(output_schema, dict) else None,
        "annotations": annotations,
    }


async def discover_catalog(endpoint_url: str) -> list[dict[str, Any]]:
    async with Client(endpoint_url) as client:
        response = await client.list_tools()
    catalog = [catalog_item(tool) for tool in response.tools]
    names = {item["name"] for item in catalog}
    if names != EXPECTED_TOOL_NAMES:
        raise RuntimeError(
            f"Refusing Web MCP bootstrap: expected tools {sorted(EXPECTED_TOOL_NAMES)}, got {sorted(names)}"
        )
    return catalog


async def _json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    expected: frozenset[int] = frozenset({200}),
) -> Any:
    kwargs: dict[str, Any] = {"headers": headers}
    if payload is not None:
        kwargs["json"] = payload
    response = await client.request(method, path, **kwargs)
    if response.status_code not in expected:
        hint = ""
        if response.status_code in {401, 403} and not os.getenv("KAIRO_ADMIN_TOKEN", "").strip():
            hint = " Set KAIRO_ADMIN_TOKEN when KAIRO authentication is enabled."
        raise RuntimeError(
            f"KAIRO Core {method} {path} returned {response.status_code}: {response.text[:1000]}.{hint}"
        )
    return response.json()


async def bootstrap() -> None:
    endpoint_url = os.getenv("KAIRO_WEB_MCP_URL", DEFAULT_WEB_MCP_URL).strip() or DEFAULT_WEB_MCP_URL
    catalog = await discover_catalog(endpoint_url)
    core_url = settings.kairo_core_url.rstrip("/")

    async with httpx.AsyncClient(base_url=core_url, timeout=20.0) as client:
        servers = await _json(client, "GET", "/v1/tool-servers", headers=_admin_headers())
        existing = next((item for item in servers if item.get("key") == WEB_SERVER_KEY), None)
        if existing is None:
            server = await _json(
                client,
                "POST",
                "/v1/tool-servers",
                headers=_admin_headers(),
                payload={
                    "key": WEB_SERVER_KEY,
                    "namespace": WEB_NAMESPACE,
                    "title": WEB_TITLE,
                    "endpoint_url": endpoint_url,
                    "transport": "mcp_streamable_http",
                    "metadata": {"managed_by": "kairo", "purpose": "research-web"},
                },
                expected=frozenset({201}),
            )
        else:
            server = existing
            if str(server.get("namespace")) != WEB_NAMESPACE:
                raise RuntimeError("Existing kairo-web ToolServer has an unexpected namespace")
            if str(server.get("endpoint_url")) != endpoint_url:
                raise RuntimeError(
                    "Existing kairo-web ToolServer endpoint differs from KAIRO_WEB_MCP_URL; "
                    "review the registry instead of silently rebinding it"
                )

        synced = await _json(
            client,
            "POST",
            f"/internal/v1/tool-servers/{server['id']}/catalog",
            headers=_internal_headers(),
            payload={"tools": catalog},
        )
        synced_keys = {str(item.get("key") or "") for item in synced}
        expected_keys = {f"{WEB_NAMESPACE}.{name}" for name in EXPECTED_TOOL_NAMES}
        if synced_keys != expected_keys:
            raise RuntimeError(
                f"Refusing Web MCP enablement: expected keys {sorted(expected_keys)}, got {sorted(synced_keys)}"
            )

        for key in sorted(expected_keys):
            encoded = urllib.parse.quote(key, safe="")
            await _json(
                client,
                "PATCH",
                f"/v1/tools/{encoded}/policy",
                headers=_admin_headers(),
                payload={
                    "enabled": True,
                    "authority_level": 1,
                    "estimated_cost_usd": "0",
                    "risk_class": "read",
                    "retry_policy": "safe_retry",
                },
            )

    print(
        "KAIRO Web MCP bootstrap complete: web.search and web.fetch are explicitly enabled as read-only A1 tools"
    )


def main() -> None:
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()
