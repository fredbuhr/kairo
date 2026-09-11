#!/usr/bin/env python3
"""End-to-end proof that public Nevolium resources cannot cross authenticated user worlds."""

from __future__ import annotations

from datetime import UTC, datetime, time as dt_time
from decimal import Decimal
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CORE = os.getenv("NEVOLIUM_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "nevolium")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "nevolium-web")
INTERNAL_TOKEN = os.getenv("NEVOLIUM_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")

USER_A = ("nevolium-dev", "nevolium-dev")
USER_B = ("nevolium-dev-2", "nevolium-dev-2")
TODAY_BUCKETS = (
    "overdue",
    "in_progress",
    "due_today",
    "planned",
    "completed_today",
    "backlog",
)


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
        headers["X-Nevolium-Internal-Token"] = INTERNAL_TOKEN
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


def today_task_ids(view: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for bucket in TODAY_BUCKETS:
        for item in view.get(bucket, []):
            task = item.get("task") or {}
            if task.get("id"):
                ids.add(str(task["id"]))
    return ids


def wait_for_memory_projection(
    message_id: str, token: str, *, timeout: float = 120.0
) -> dict[str, Any]:
    """Prove the Worker can start system memory Tasks while public auth stays enabled."""

    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        status_code, body = json_request(
            "GET",
            f"/v1/memory/projections/conversation-messages/{message_id}",
            token=token,
            expected={200, 404},
        )
        last = body
        if status_code == 200:
            rows = body.get("projectors") or []
            if (
                len(rows) == 2
                and {str(row.get("projector")) for row in rows} == {"mem0", "graphiti"}
                and all(row.get("status") == "projected" for row in rows)
            ):
                return body
        time.sleep(0.5)
    raise AssertionError(
        f"Authenticated memory projection did not complete for {message_id}: {last!r}"
    )


def seed_legacy_dispatch(project_id: str, owner_ref: str, invocation_id: str) -> dict[str, str]:
    """Model a forged Task already queued before this fix, using only integration fixtures."""

    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "nevolium-core", "python", "-",
         json.dumps({"project_id": project_id, "owner_ref": owner_ref, "invocation_id": invocation_id})],
        input='''
import asyncio
import json
import sys
import uuid
from nevolium_core.db import SessionFactory, engine
from nevolium_core.models import Task, WorkflowExecution

async def seed():
    values = json.loads(sys.argv[1])
    try:
        async with SessionFactory() as session:
            task = Task(
                id=uuid.uuid4(), project_id=uuid.UUID(values["project_id"]),
                title="Legacy foreign dispatch regression", status="queued",
                owner_type="user", owner_ref=values["owner_ref"],
                input={"capability": "tool.invoke", "tool_invocation_id": values["invocation_id"]},
            )
            session.add(task)
            await session.flush()
            execution = WorkflowExecution(
                task_id=task.id, workflow_id=f"nevolium-task-{task.id}",
                correlation_id=uuid.uuid4(), status="queued",
            )
            session.add(execution)
            await session.commit()
            print(json.dumps({"task_id": str(task.id), "workflow_id": execution.workflow_id}))
    finally:
        await engine.dispose()

asyncio.run(seed())
''',
        text=True, capture_output=True, timeout=30,
    )
    if result.returncode:
        raise AssertionError(f"Legacy dispatch fixture failed: {result.stderr[-4000:]}")
    return json.loads(result.stdout)


def prove_dispatch_isolation(
    token_a: str, token_b: str, project_b: dict[str, Any], task_b: dict[str, Any],
    invocation_a: dict[str, Any], invocation_b: dict[str, Any],
) -> None:
    foreign_id = invocation_a["invocation"]["id"]
    for capability in (
        "tool.invoke", "document.ingest", "memory.project", "assistant.route.semantic",
        "news.brief", "research.autonomous", "unknown.future-capability",
    ):
        json_request(
            "POST", "/v1/tasks", token=token_b, expected={422},
            payload={"project_id": project_b["id"], "title": "Forged dispatch",
                     "input": {"capability": capability, "tool_invocation_id": foreign_id}},
        )
    for owner in ("system", "agent"):
        json_request(
            "POST", "/v1/tasks", token=token_b, expected={422},
            payload={"project_id": project_b["id"], "title": "Forged identity", "owner_type": owner},
        )

    legacy = seed_legacy_dispatch(project_b["id"], task_b["owner_ref"], foreign_id)
    for invocation_status in ("pending", "completed"):
        if invocation_status == "completed":
            json_request(
                "POST", f"/internal/v1/tool-invocations/{foreign_id}/complete", internal=True,
                payload={"result": {"value": "owner-a-private-sentinel"}},
            )
        # Both new dispatch and an old queued workflow fail before reaching an activity.
        json_request("POST", f"/v1/tasks/{legacy['task_id']}/run", token=token_b, expected={409})
        json_request("POST", f"/internal/v1/executions/{legacy['workflow_id']}/start", internal=True, expected={409})
        json_request(
            "POST", f"/internal/v1/tool-invocations/{foreign_id}/fail", internal=True, expected={409},
            payload={"task_id": legacy["task_id"], "error": "foreign failure must not mutate A"},
        )
        _, foreign = json_request("GET", f"/v1/tool-invocations/{foreign_id}", token=token_a)
        assert foreign["status"] == invocation_status and foreign["last_error"] is None, foreign
        json_request("GET", f"/v1/tool-invocations/{foreign_id}", token=token_b, expected={404})
        _, artifacts = json_request("GET", f"/v1/tasks/{legacy['task_id']}/artifacts", token=token_b)
        assert artifacts == [], artifacts
        _, blocked = json_request("GET", f"/v1/tasks/{legacy['task_id']}", token=token_b)
        assert blocked["status"] == "queued", blocked

    # A real Worker must still replay B's own completed result into B's canonical Artifact.
    own_id = invocation_b["invocation"]["id"]
    json_request(
        "POST", f"/internal/v1/tool-invocations/{own_id}/complete", internal=True,
        payload={"result": {"value": "owner-b-replay-sentinel"}},
    )
    own_task = invocation_b["task_id"]
    json_request("POST", f"/v1/tasks/{own_task}/run", token=token_b)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        _, task = json_request("GET", f"/v1/tasks/{own_task}", token=token_b)
        if task["status"] == "completed":
            break
        assert task["status"] in {"queued", "running"}, task
        time.sleep(0.5)
    else:
        raise AssertionError(f"Legitimate tool replay did not complete: {task}")
    _, artifacts = json_request("GET", f"/v1/tasks/{own_task}/artifacts", token=token_b)
    assert len(artifacts) == 1 and artifacts[0]["content"]["replayed"] is True, artifacts
    assert artifacts[0]["content"]["result"] == {"value": "owner-b-replay-sentinel"}, artifacts
    json_request("GET", f"/v1/tasks/{own_task}/artifacts", token=token_a, expected={404})


def main() -> int:
    wait_for(f"{KEYCLOAK}/realms/{REALM}/.well-known/openid-configuration", "Keycloak realm")
    wait_for(f"{CORE}/health/ready", "Nevolium Core")

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
    assert task_a["priority"] == 2 and task_a["due_at"] is None, task_a
    assert task_b["priority"] == 2 and task_b["planned_start_at"] is None, task_b

    # New admission summaries inherit the real authenticated owner boundary.
    json_request("GET", "/v1/model-admission", expected={401})
    _, admitted = json_request("POST", "/internal/v1/policy/authorize", internal=True, payload={
        "task_id": task_a["id"], "idempotency_key": "isolation-model-reservation-a",
        "action": "model.invoke", "resource_type": "model_alias", "resource_id": "smart",
        "authority_level": 1, "estimated_cost_usd": "0.01",
    })
    assert admitted["allowed"], admitted
    _, admission_a = json_request("GET", "/v1/model-admission", token=token_a)
    _, admission_b = json_request("GET", "/v1/model-admission", token=token_b)
    assert admission_a["active_calls"] == 1 and Decimal(admission_a["daily_exposure_usd"]) == Decimal("0.01")
    assert admission_b["active_calls"] == 0 and Decimal(admission_b["daily_exposure_usd"]) == 0

    # Daily planning is canonical Task state and remains owner-scoped end-to-end.
    utc_day = datetime.now(UTC).date()
    day_text = utc_day.isoformat()
    due_midday = datetime.combine(utc_day, dt_time(hour=12), tzinfo=UTC).isoformat()
    _, planned_a = json_request(
        "PATCH",
        f"/v1/tasks/{task_a['id']}",
        token=token_a,
        payload={"priority": 4, "due_at": due_midday},
        expected={200},
    )
    assert planned_a["priority"] == 4 and planned_a["due_at"], planned_a
    json_request(
        "PATCH",
        f"/v1/tasks/{task_a['id']}",
        token=token_b,
        payload={"priority": 0},
        expected={404},
    )

    _, today_a = json_request(
        "GET",
        f"/v1/today?day={day_text}&timezone=UTC",
        token=token_a,
        expected={200},
    )
    _, today_b = json_request(
        "GET",
        f"/v1/today?day={day_text}&timezone=UTC",
        token=token_b,
        expected={200},
    )
    assert task_a["id"] in {item["task"]["id"] for item in today_a["due_today"]}, today_a
    assert task_b["id"] not in today_task_ids(today_a), today_a
    assert task_a["id"] not in today_task_ids(today_b), today_b
    assert task_b["id"] in {item["task"]["id"] for item in today_b["backlog"]}, today_b

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

    prove_dispatch_isolation(token_a, token_b, project_b, task_b, invocation_a, invocation_b)

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
    projection = wait_for_memory_projection(message_id, token_a)
    assert {row["projector"] for row in projection["projectors"]} == {
        "mem0",
        "graphiti",
    }, projection
    assert all(
        row["metadata"].get("backend") == "deterministic-stub"
        for row in projection["projectors"]
    ), projection
    json_request(
        "GET",
        f"/v1/memory/projections/conversation-messages/{message_id}",
        token=token_b,
        expected={404},
    )

    # Manual completion participates in Today, but status control becomes Worker-owned once a
    # Temporal WorkflowExecution exists.
    _, completed_a = json_request(
        "PATCH",
        f"/v1/tasks/{task_a['id']}",
        token=token_a,
        payload={"status": "completed"},
        expected={200},
    )
    assert completed_a["status"] == "completed" and completed_a["completed_at"], completed_a
    _, today_completed_a = json_request(
        "GET",
        f"/v1/today?day={day_text}&timezone=UTC",
        token=token_a,
        expected={200},
    )
    assert task_a["id"] in {
        item["task"]["id"] for item in today_completed_a["completed_today"]
    }, today_completed_a

    json_request(
        "POST",
        f"/v1/tasks/{task_b['id']}/run",
        token=token_b,
        expected={200},
    )
    json_request(
        "PATCH",
        f"/v1/tasks/{task_b['id']}",
        token=token_b,
        payload={"status": "completed"},
        expected={409},
    )

    print(
        "PASS: two authenticated users are isolated across planning/Today, Relationships, "
        "approvals, budgets, ToolInvocations/idempotency, authenticated Worker-driven memory "
        "projection, memory read isolation and detailed system diagnostics; Workflow-managed "
        "Task status remains Worker-owned; public capability forgery and legacy foreign "
        "dispatch/failure are rejected while legitimate completed tool replay succeeds"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
