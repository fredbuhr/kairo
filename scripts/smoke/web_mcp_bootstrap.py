#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

CORE = "http://localhost:8000"
INTERNAL_TOKEN = os.getenv("KAIRO_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")
INTERNAL = {"X-Kairo-Internal-Token": INTERNAL_TOKEN}


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read().decode())
    if status != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {body}")
    return body


def wait_ready() -> None:
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            if request("GET", "/health/ready")["status"] == "ready":
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Core did not become ready")


def catalog(*, drift: bool = False) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "query": {"type": "string", "minLength": 2, "maxLength": 500},
        "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
    }
    if drift:
        properties["freshness"] = {"type": "string", "default": ""}
    return {
        "tools": [
            {
                "name": "search",
                "title": "Search the public web",
                "description": "Read-only public-web source discovery",
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "output_schema": None,
                "annotations": {"readOnlyHint": True, "openWorldHint": True},
            }
        ]
    }


def main() -> None:
    wait_ready()

    first = request(
        "POST",
        "/internal/v1/system-tools/web/catalog",
        headers=INTERNAL,
        payload=catalog(),
    )
    tool = first["tool"]
    assert first["initial_activation"] is True, first
    assert first["server_enabled"] is True, first
    assert tool["key"] == "web.search", tool
    assert tool["enabled"] is True, tool
    assert tool["authority_level"] == 1, tool
    assert tool["risk_class"] == "read", tool
    assert tool["retry_policy"] == "safe_retry", tool
    first_schema_hash = tool["schema_hash"]

    second = request(
        "POST",
        "/internal/v1/system-tools/web/catalog",
        headers=INTERNAL,
        payload=catalog(),
    )
    assert second["server_id"] == first["server_id"], (first, second)
    assert second["initial_activation"] is False, second
    assert second["tool"]["enabled"] is True, second
    assert second["tool"]["schema_hash"] == first_schema_hash, second

    servers = request("GET", "/v1/tool-servers")
    web_server = next(item for item in servers if item["key"] == "kairo-web")
    assert web_server["namespace"] == "web", web_server
    assert web_server["endpoint_url"] == "http://kairo-web-mcp:8765/mcp", web_server

    project = request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "Web MCP bootstrap smoke", "status": "active"},
    )
    research = request(
        "POST",
        "/v1/tasks",
        expected=201,
        payload={
            "project_id": project["id"],
            "title": "Research with first-party Web MCP",
            "owner_type": "agent",
            "owner_ref": "kairo.research-agent",
            "authority_ceiling": 1,
            "budget_usd": "0.01",
            "input": {
                "capability": "research.autonomous",
                "query": "Find public evidence about KAIRO",
                "max_tool_calls": 2,
                "allowed_tool_keys": [],
                "model_alias": "local-fast",
                "estimated_model_cost_usd": "0.01",
                "authority_level": 1,
                "estimated_cost_usd": "0.01",
            },
        },
    )
    context = request(
        "GET", f"/internal/v1/research/tasks/{research['id']}/context", headers=INTERNAL
    )
    assert {item["key"] for item in context["tools"]} == {"web.search"}, context

    drifted = request(
        "POST",
        "/internal/v1/system-tools/web/catalog",
        headers=INTERNAL,
        payload=catalog(drift=True),
    )
    assert drifted["initial_activation"] is False, drifted
    assert drifted["tool"]["schema_hash"] != first_schema_hash, drifted
    assert drifted["tool"]["enabled"] is False, drifted

    context_after_drift = request(
        "GET", f"/internal/v1/research/tasks/{research['id']}/context", headers=INTERNAL
    )
    assert context_after_drift["tools"] == [], context_after_drift

    print(
        "PASS: first-party Web MCP bootstrap is idempotent, initially A1/read, visible to research, "
        "and schema drift disables it without automatic reactivation"
    )


if __name__ == "__main__":
    main()
