#!/usr/bin/env python3
"""Proof for fail-closed MCP server registration and policy management."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

CORE = "http://localhost:8000"


def json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(CORE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
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

    json_request(
        "POST",
        "/v1/tool-servers",
        expected=422,
        payload={
            "key": "Invalid Key",
            "title": "Invalid",
            "endpoint_url": "https://mcp.invalid.example/mcp",
        },
    )
    json_request(
        "POST",
        "/v1/tool-servers",
        expected=422,
        payload={
            "key": "fixture.invalid-url",
            "title": "Invalid URL",
            "endpoint_url": "file:///etc/passwd",
        },
    )

    _, server = json_request(
        "POST",
        "/v1/tool-servers",
        expected=201,
        payload={
            "key": "fixture.tools-workspace",
            "title": "Tools Workspace Fixture",
            "endpoint_url": "https://mcp.fixture.invalid/mcp",
            "transport": "streamable-http",
            "auth_mode": "none",
            "metadata": {"purpose": "smoke"},
        },
    )
    assert server["key"] == "fixture.tools-workspace", server
    assert server["enabled"] is False, server
    assert int(server["catalog_generation"]) == 0, server

    # Registration is unique and must not mutate the existing record on conflict.
    json_request(
        "POST",
        "/v1/tool-servers",
        expected=409,
        payload={
            "key": "fixture.tools-workspace",
            "title": "Duplicate",
            "endpoint_url": "https://other.invalid/mcp",
        },
    )

    _, servers = json_request("GET", "/v1/tool-servers")
    listed = next(item for item in servers if item["key"] == "fixture.tools-workspace")
    assert listed["enabled"] is False, listed

    _, enabled = json_request(
        "PATCH",
        "/v1/tool-servers/fixture.tools-workspace/policy",
        payload={"enabled": True},
    )
    assert enabled["enabled"] is True, enabled

    _, disabled = json_request(
        "PATCH",
        "/v1/tool-servers/fixture.tools-workspace/policy",
        payload={"enabled": False},
    )
    assert disabled["enabled"] is False, disabled

    # An unknown server cannot be enabled by creating state implicitly.
    json_request(
        "PATCH",
        "/v1/tool-servers/fixture.missing/policy",
        expected=404,
        payload={"enabled": True},
    )

    print("KAIRO fail-closed MCP server registration + policy proof passed")


if __name__ == "__main__":
    main()
