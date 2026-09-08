#!/usr/bin/env python3
"""Integration proof for KAIRO's canonical MCP tool registry and deny-by-default policy."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CORE = "http://localhost:8000"
INTERNAL = {"X-Kairo-Internal-Token": "development-only-change-me"}


def json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read().decode("utf-8"))
    if status != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {body}")
    return status, body


def wait_ready() -> None:
    deadline = time.time() + 90
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            _, body = json_request("GET", "/health/ready")
            if body["status"] == "ready":
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"KAIRO Core did not become ready: {last_error}")


def main() -> None:
    wait_ready()

    _, project = json_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "MCP registry smoke", "status": "active"},
    )

    _, server = json_request(
        "POST",
        "/v1/tool-servers",
        expected=201,
        payload={
            "key": "smoke-server",
            "namespace": "smoke",
            "title": "Smoke MCP Server",
            "endpoint_url": "http://fake-mcp:8765/mcp",
            "transport": "mcp_streamable_http",
        },
    )
    assert server["catalog_generation"] == 0, server

    _, catalog = json_request(
        "POST",
        f"/internal/v1/tool-servers/{server['id']}/catalog",
        headers=INTERNAL,
        payload={
            "tools": [
                {
                    "name": "search",
                    "title": "Search",
                    "description": "Read-only search tool",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                    "annotations": {"readOnlyHint": True, "idempotentHint": True},
                },
                {
                    "name": "send",
                    "title": "Send",
                    "description": "Side-effecting send tool",
                    "input_schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                    "annotations": {},
                },
            ]
        },
    )
    assert len(catalog) == 2, catalog
    read_tool = next(item for item in catalog if item["key"] == "smoke.search")
    write_tool = next(item for item in catalog if item["key"] == "smoke.send")
    assert read_tool["enabled"] is False, read_tool
    assert read_tool["risk_class"] == "read", read_tool
    assert read_tool["authority_level"] == 1, read_tool
    assert read_tool["retry_policy"] == "safe_retry", read_tool
    assert write_tool["enabled"] is False, write_tool
    assert write_tool["risk_class"] == "write", write_tool
    assert write_tool["authority_level"] == 2, write_tool
    assert write_tool["retry_policy"] == "no_retry", write_tool

    # Discovery must never imply permission to use a tool.
    json_request(
        "POST",
        "/v1/tool-invocations",
        expected=409,
        payload={
            "project_id": project["id"],
            "tool_key": "smoke.search",
            "input": {"query": "kairo"},
        },
    )

    encoded_key = urllib.parse.quote("smoke.search", safe="")
    _, enabled = json_request(
        "PATCH",
        f"/v1/tools/{encoded_key}/policy",
        payload={
            "enabled": True,
            "authority_level": 1,
            "risk_class": "read",
            "retry_policy": "safe_retry",
        },
    )
    assert enabled["enabled"] is True, enabled

    _, created = json_request(
        "POST",
        "/v1/tool-invocations",
        expected=201,
        payload={
            "project_id": project["id"],
            "tool_key": "smoke.search",
            "input": {"query": "kairo"},
            "idempotency_key": "smoke-tool-invocation-1",
        },
    )
    invocation = created["invocation"]
    task_id = created["task_id"]
    assert invocation["status"] == "pending", invocation
    assert invocation["idempotency_key"] == "smoke-tool-invocation-1", invocation

    _, task = json_request("GET", f"/v1/tasks/{task_id}")
    assert task["input"]["capability"] == "tool.invoke", task
    assert task["input"]["tool_key"] == "smoke.search", task
    assert task["authority_ceiling"] == 1, task

    # Same key + same logical invocation returns the canonical existing record.
    _, replay = json_request(
        "POST",
        "/v1/tool-invocations",
        expected=201,
        payload={
            "project_id": project["id"],
            "tool_key": "smoke.search",
            "input": {"query": "kairo"},
            "idempotency_key": "smoke-tool-invocation-1",
        },
    )
    assert replay["invocation"]["id"] == invocation["id"], replay
    assert replay["task_id"] == task_id, replay

    print("MCP tool registry integration PASS")


if __name__ == "__main__":
    main()
