#!/usr/bin/env python3
"""End-to-end proof that public KAIRO resources cannot cross authenticated user worlds."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CORE = os.getenv("KAIRO_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "kairo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "kairo-web")
INTERNAL_TOKEN = os.getenv("KAIRO_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")

USER_A = ("kairo-dev", "kairo-dev")
USER_B = ("kairo-dev-2", "kairo-dev-2")


def request(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    expected: set[int] | None = None,
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            status_code = response.status
            payload = response.read()
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        payload = exc.read()
    allowed = expected or {200}
    if status_code not in allowed:
        raise AssertionError(
            f"{method} {url} returned {status_code}, expected {sorted(allowed)}: {payload[:1000]!r}"
        )
    return status_code, payload


def json_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    expected: set[int] | None = None,
    internal: bool = False,
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if internal:
        headers["X-Kairo-Internal-Token"] = INTERNAL_TOKEN
    status_code, raw = request(
        method,
        f"{CORE}{path}",
        body=body,
        headers=headers,
        expected=expected,
    )
    return status_code, json.loads(raw.decode()) if raw else {}


def wait_for(url: str, label: str, *, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status_code, _ = request("GET", url, expected={200, 503})
            if status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001 - surfaced on timeout
            last = exc
        time.sleep(1.0)
    raise AssertionError(f"Timed out waiting for {label}: {last!r}")


def access_token(username: str, password: str) -> str:
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        }
    ).encode()
    _, raw = request(
        "POST",
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        body=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        expected={200},
    )
    token = str(json.loads(raw.decode()).get("access_token") or "")
    if not token:
        raise AssertionError(f"Keycloak did not return an access token for {username}")
    return token


def main() -> int:
    wait_for(f"{KEYCLOAK}/realms/{REALM}/.well-known/openid-configuration", "Keycloak realm")
    wait_for(f"{CORE}/health/ready", "KAIRO Core")

    token_a = access_token(*USER_A)
    token_b = access_token(*USER_B)

    # Detailed deployment diagnostics are admin-only; liveness/readiness remain public.
    json_request("GET", "/v1/system/architecture", token=token_a, expected={200})
    json_request("GET", "/v1/system/architecture", token=token_b, expected={403})
    json_request("GET", "/v1/system/outbox", token=token_b, expected={403})

    _, project_a = json_request(
        "POST",
        "/v1/projects",
        token=token_a,
        payload={"name": "Isolation A"},
        expected={201},
    )
    _, project_b = json_request(
        "POST",
        "/v1/projects",
        token=token_b,
        payload={"name": "Isolation B"},
        expected={201},
    )

    _, task_a = json_request(
        "POST",
        "/v1/tasks",
        token=token_a,
        payload={
            "project_id": project_a["id"],
            "title": "Owner A protected task",
            "authority_ceiling": 2,
            "budget_usd": "1.00",
        },
        expected={201},
    )
    _, task_b = json_request(
        "POST",
        "/v1/tasks",
        token=token_b,
        payload={
            "project_id": project_b["id"],
            "title": "Owner B protected task",
            "authority_ceiling": 2,
            "budget_usd": "1.00",
        },
        expected={201},
    )

    # Relationship endpoints fail closed for foreign or mixed-owner endpoints.
    _, relationship = json_request(
        "POST",
        "/v1/relationships",
        token=token_a,
        payload={
            "source_type": "project",
            "source_id": project_a["id"],
            "relation_type": "contains",
            "target_type": "task",
            "target_id": task_a["id"],
        },
        expected={201},
    )
    assert relationship["source_id"] == project_a["id"]
    json_request(
        "POST",
        "/v1/relationships",
        token=token_b,
        payload={
            "source_type": "project",
            "source_id": project_a["id"],
            "relation_type": "contains",
            "target_type": "task",
            "target_id": task_a["id"],
        },
        expected={404},
    )
    json_request(
        "POST",
        "/v1/relationships",
        token=token_a,
        payload={
            "source_type": "project",
            "source_id": project_a["id"],
            "relation_type": "cross-owner-forbidden",
            "target_type": "task",
            "target_id": task_b["id"],
        },
        expected={404},
    )

    # Approvals and budgets inherit ownership from Task -> Project.
    _, approval_a = json_request(
        "POST",
        "/v1/approval-requests",
        token=token_a,
        payload={
            "task_id": task_a["id"],
            "action": "integration.owner-proof",
            "resource_type": "task",
            "resource_id": task_a["id"],
            "authority_level": 2,
            "reason": "Prove owner-scoped approval control plane",
            "scope": {"proof": "owner-a"},
        },
        expected={201},
    )
    json_request(
        "POST",
        "/v1/approval-requests",
        token=token_b,
        payload={
            "task_id": task_a["id"],
            "action": "integration.foreign",
            "resource_type": "task",
            "authority_level": 1,
            "reason": "Must not cross owner scope",
        },
        expected={404},
    )
    json_request(
        "GET",
        f"/v1/approval-requests?task_id={task_a['id']}",
        token=token_b,
        expected={404},
    )
    json_request(
        "POST",
        f"/v1/approval-requests/{approval_a['id']}/decision",
        token=token_b,
        payload={"decision": "approved", "note": "foreign decision must fail"},
        expected={404},
    )
    json_request("GET", f"/v1/tasks/{task_a['id']}/budget", token=token_b, expected={404})
    json_request("GET", f"/v1/tasks/{task_a['id']}/budget", token=token_a, expected={200})

    # Deployment-global tool registry is readable without revealing endpoint URLs.
    _, server = json_request(
        "POST",
        "/v1/tool-servers",
        token=token_a,
        payload={
            "key": "isolation-fixture",
            "namespace": "isolation",
            "title": "Isolation fixture",
            "endpoint_url": "http://private-tool-service.invalid/mcp",
        },
        expected={201},
    )
    json_request(
        "POST",
        f"/internal/v1/tool-servers/{server['id']}/catalog",
        internal=True,
        payload={
            "tools": [
                {
                    "name": "read",
                    "title": "Read fixture",
                    "input_schema": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                    "annotations": {"readOnlyHint": True, "idempotentHint": True},
                }
            ]
        },
        expected={200},
    )
    json_request(
        "PATCH",
        "/v1/tools/isolation.read/policy",
        token=token_a,
        payload={
            "enabled": True,
            "authority_level": 1,
            "estimated_cost_usd": "0",
            "risk_class": "read",
            "retry_policy": "safe_retry",
        },
        expected={200},
    )
    _, visible_servers = json_request("GET", "/v1/tool-servers", token=token_b, expected={200})
    visible = next(item for item in visible_servers if item["id"] == server["id"])
    assert "endpoint_url" not in visible and "metadata_json" not in visible, visible

    shared_key = "multi-user-shared-idempotency-key"
    _, invocation_a = json_request(
        "POST",
        "/v1/tool-invocations",
        token=token_a,
        payload={
            "project_id": project_a["id"],
            "tool_key": "isolation.read",
            "input": {"value": "A"},
            "idempotency_key": shared_key,
        },
        expected={201},
    )
    _, invocation_b = json_request(
        "POST",
        "/v1/tool-invocations",
        token=token_b,
        payload={
            "project_id": project_b["id"],
            "tool_key": "isolation.read",
            "input": {"value": "B"},
            "idempotency_key": shared_key,
        },
        expected={201},
    )
    assert invocation_a["invocation"]["id"] != invocation_b["invocation"]["id"]
    json_request(
        "POST",
        "/v1/tool-invocations",
        token=token_b,
        payload={
            "project_id": project_a["id"],
            "tool_key": "isolation.read",
            "input": {"value": "foreign"},
        },
        expected={404},
    )
    json_request(
        "GET",
        f"/v1/tool-invocations/{invocation_a['invocation']['id']}",
        token=token_b,
        expected={404},
    )
    json_request(
        "GET",
        f"/v1/tool-invocations/{invocation_a['invocation']['id']}",
        token=token_a,
        expected={200},
    )

    # Memory projection reads are tied back to the owning Conversation subject.
    _, command = json_request(
        "POST",
        "/v1/assistant/commands",
        token=token_a,
        payload={"text": "news today", "locale": "en-US", "output": "text"},
        expected={202},
    )
    _, messages = json_request(
        "GET",
        f"/v1/conversations/{command['conversation_id']}/messages",
        token=token_a,
        expected={200},
    )
    assert messages, messages
    message_id = messages[0]["id"]
    json_request(
        "GET",
        f"/v1/memory/projections/conversation-messages/{message_id}",
        token=token_a,
        expected={200},
    )
    json_request(
        "GET",
        f"/v1/memory/projections/conversation-messages/{message_id}",
        token=token_b,
        expected={404},
    )

    print(
        "PASS: two authenticated users are isolated across Relationships, approvals, budgets, "
        "ToolInvocations/idempotency, memory projection reads and detailed system diagnostics"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
