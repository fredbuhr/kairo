#!/usr/bin/env python3
"""Runtime proof for subject-owned ToolInvocation idempotency and read isolation.

ToolServer/ToolDefinition remain one shared deployment control plane. Two authenticated users invoke
that same logical read-only contract with the same caller-selected idempotency key; KAIRO must create
independent user-world ToolInvocations and return foreign invocation IDs as 404.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

CORE = os.getenv("KAIRO_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "kairo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "kairo-web")
USER_A = os.getenv("KEYCLOAK_DEV_USERNAME", "kairo-dev")
PASSWORD_A = os.getenv("KEYCLOAK_DEV_PASSWORD", "kairo-dev")
USER_B = os.getenv("KEYCLOAK_ALT_USERNAME", "kairo-alt")
PASSWORD_B = os.getenv("KEYCLOAK_ALT_PASSWORD", "kairo-alt")


def config_value(name: str, default: str | None = None) -> str:
    direct = os.getenv(name)
    if direct:
        return direct
    env_path = Path(".env")
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    if default is not None:
        return default
    raise RuntimeError(f"{name} is required")


def request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    internal: bool = False,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if internal:
        headers["X-Kairo-Internal-Token"] = config_value(
            "KAIRO_INTERNAL_TOKEN",
            "CHANGE_ME_INTERNAL_TOKEN",
        )
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(CORE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status_code = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw = exc.read().decode("utf-8")
    body = json.loads(raw) if raw else None
    if status_code != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status_code}: {body!r}")
    return body


def access_token(username: str, password: str) -> str:
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data=form,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = str(payload.get("access_token") or "")
    if not token:
        raise AssertionError(f"Keycloak did not return a token for {username}")
    return token


def create_project(token: str, name: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/v1/projects",
        token=token,
        expected=201,
        payload={"name": name, "status": "active", "summary": None, "parent_id": None},
    )


def main() -> None:
    token_a = access_token(USER_A, PASSWORD_A)
    token_b = access_token(USER_B, PASSWORD_B)
    nonce = uuid.uuid4().hex[:10]
    project_a = create_project(token_a, f"Tool owner A {nonce}")
    project_b = create_project(token_b, f"Tool owner B {nonce}")

    server_key = f"ownership.{nonce}"
    namespace = f"own{nonce}"
    server = request_json(
        "POST",
        "/v1/tool-servers",
        token=token_a,
        expected=201,
        payload={
            "key": server_key,
            "namespace": namespace,
            "title": "Ownership shared MCP fixture",
            # No request is ever sent to this transport in this proof; only the KAIRO registry and
            # user-world invocation ledger are exercised.
            "endpoint_url": "http://mcp-ownership-fixture.invalid/mcp",
            "transport": "mcp_streamable_http",
            "metadata": {"fixture": "two-user-tool-invocation"},
        },
    )
    assert server["enabled"] is False, server

    catalog = request_json(
        "POST",
        f"/internal/v1/tool-servers/{server['id']}/catalog",
        internal=True,
        payload={
            "tools": [
                {
                    "name": "read_fixture",
                    "title": "Read ownership fixture",
                    "description": "Read-only tool used only to prove invocation ownership",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                    "output_schema": {"type": "object"},
                    "annotations": {"readOnlyHint": True},
                }
            ]
        },
    )
    assert len(catalog) == 1, catalog
    tool = catalog[0]
    assert tool["risk_class"] == "read" and int(tool["authority_level"]) == 1, tool

    request_json(
        "PATCH",
        f"/v1/tool-servers/{urllib.parse.quote(server_key, safe='')}/policy",
        token=token_a,
        payload={"enabled": True},
    )
    request_json(
        "PATCH",
        f"/v1/tools/{urllib.parse.quote(tool['key'], safe='')}/policy",
        token=token_a,
        payload={"enabled": True},
    )

    shared_key = f"same-human-key-{nonce}"
    input_payload = {"query": "same logical request"}
    invocation_a = request_json(
        "POST",
        "/v1/tool-invocations",
        token=token_a,
        expected=201,
        payload={
            "project_id": project_a["id"],
            "tool_key": tool["key"],
            "input": input_payload,
            "idempotency_key": shared_key,
        },
    )
    invocation_b = request_json(
        "POST",
        "/v1/tool-invocations",
        token=token_b,
        expected=201,
        payload={
            "project_id": project_b["id"],
            "tool_key": tool["key"],
            "input": input_payload,
            "idempotency_key": shared_key,
        },
    )
    id_a = invocation_a["invocation"]["id"]
    id_b = invocation_b["invocation"]["id"]
    assert id_a != id_b, (invocation_a, invocation_b)
    assert invocation_a["task_id"] != invocation_b["task_id"], (invocation_a, invocation_b)

    # Same subject + exact same request reuses the same canonical invocation.
    replay_a = request_json(
        "POST",
        "/v1/tool-invocations",
        token=token_a,
        expected=201,
        payload={
            "project_id": project_a["id"],
            "tool_key": tool["key"],
            "input": input_payload,
            "idempotency_key": shared_key,
        },
    )
    assert replay_a["invocation"]["id"] == id_a, replay_a
    assert replay_a["task_id"] == invocation_a["task_id"], replay_a

    # Reusing A's idempotency key with a different binding still fails inside A's own namespace.
    request_json(
        "POST",
        "/v1/tool-invocations",
        token=token_a,
        expected=409,
        payload={
            "project_id": project_a["id"],
            "tool_key": tool["key"],
            "input": {"query": "different request"},
            "idempotency_key": shared_key,
        },
    )

    # Foreign invocation identifiers are indistinguishable from absent ones.
    request_json("GET", f"/v1/tool-invocations/{id_b}", token=token_a, expected=404)
    request_json("GET", f"/v1/tool-invocations/{id_a}", token=token_b, expected=404)
    own_a = request_json("GET", f"/v1/tool-invocations/{id_a}", token=token_a)
    own_b = request_json("GET", f"/v1/tool-invocations/{id_b}", token=token_b)
    assert own_a["id"] == id_a and own_b["id"] == id_b

    print("KAIRO two-user ToolInvocation ownership/idempotency proof passed")


if __name__ == "__main__":
    main()
