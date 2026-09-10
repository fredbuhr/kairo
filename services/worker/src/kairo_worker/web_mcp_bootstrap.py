from __future__ import annotations

import asyncio
from typing import Any

import httpx
from mcp import Client

from .config import settings


def _tool_catalog_item(tool: Any) -> dict[str, Any]:
    annotations: dict[str, Any] = {}
    if tool.annotations is not None:
        annotations = tool.annotations.model_dump(mode="json", by_alias=True, exclude_none=True)
    return {
        "name": tool.name,
        "title": tool.title,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "output_schema": tool.output_schema,
        "annotations": annotations,
    }


async def discover_catalog(endpoint: str) -> dict[str, Any]:
    async with Client(endpoint) as client:
        listed = await client.list_tools()
    return {"tools": [_tool_catalog_item(tool) for tool in listed.tools]}


async def bootstrap_once() -> dict[str, Any]:
    catalog = await discover_catalog(settings.kairo_web_mcp_url)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/system-tools/web/catalog",
            headers={"X-Kairo-Internal-Token": settings.kairo_internal_token},
            json=catalog,
        )
        response.raise_for_status()
        return response.json()


async def main_async() -> None:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            result = await bootstrap_once()
            tool = result.get("tool") if isinstance(result.get("tool"), dict) else {}
            print(
                "KAIRO Web MCP bootstrap ready: "
                f"{tool.get('key', 'web.search')} enabled={tool.get('enabled')} "
                f"schema={str(tool.get('schema_hash') or '')[:12]}"
            )
            return
        except (httpx.HTTPError, OSError, RuntimeError) as exc:
            last_error = exc
            await asyncio.sleep(1.0)
    raise RuntimeError(f"KAIRO Web MCP bootstrap failed after bounded retries: {last_error}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
