#!/usr/bin/env python3
"""Prove that authenticated KAIRO users cannot observe or mutate each other's canonical world.

The proof uses two real Keycloak identities against one Core/PostgreSQL instance. It deliberately
covers the project-root ownership chain plus polymorphic relationships and the graph read model,
because authenticating requests without tenant-scoping these surfaces would still leak the Cockpit.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from typing import Any

CORE = os.getenv("KAIRO_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "kairo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "kairo-web")
USER_A = os.getenv("KEYCLOAK_DEV_USERNAME", "kairo-dev")
PASSWORD_A = os.getenv("KEYCLOAK_DEV_PASSWORD", "kairo-dev")
USER_B = os.getenv("KEYCLOAK_ALT_USERNAME", "kairo-alt")
PASSWORD_B = os.getenv("KEYCLOAK_ALT_PASSWORD", "kairo-alt")


def request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(CORE + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status_code = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw = exc.read().decode("utf-8")
    parsed = json.loads(raw) if raw else None
    if status_code != expected:
        raise AssertionError(
            f"{method} {path}: expected {expected}, got {status_code}: {parsed!r}"
        )
    return parsed


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


def ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("id") or row.get("task_id") or "") for row in rows}


def grouped_today_ids(payload: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for key in ("overdue", "due_today", "planned_today", "important"):
        result.update(str(row["id"]) for row in payload.get(key, []))
    return result


def graph_node_ids(payload: dict[str, Any]) -> set[str]:
    return {str(row["id"]) for row in payload.get("nodes", [])}


def main() -> None:
    token_a = access_token(USER_A, PASSWORD_A)
    token_b = access_token(USER_B, PASSWORD_B)
    nonce = uuid.uuid4().hex[:10]
    project_name_a = f"Ownership A {nonce}"
    project_name_b = f"Ownership B {nonce}"

    project_a = request_json(
        "POST",
        "/v1/projects",
        token=token_a,
        expected=201,
        payload={"name": project_name_a, "status": "active", "summary": "tenant A", "parent_id": None},
    )
    project_b = request_json(
        "POST",
        "/v1/projects",
        token=token_b,
        expected=201,
        payload={"name": project_name_b, "status": "active", "summary": "tenant B", "parent_id": None},
    )

    projects_a = request_json("GET", "/v1/projects", token=token_a)
    projects_b = request_json("GET", "/v1/projects", token=token_b)
    assert project_a["id"] in ids(projects_a), projects_a
    assert project_b["id"] not in ids(projects_a), projects_a
    assert project_b["id"] in ids(projects_b), projects_b
    assert project_a["id"] not in ids(projects_b), projects_b

    # Foreign project IDs collapse to 404 rather than confirming that another tenant owns them.
    request_json(
        "POST",
        "/v1/projects",
        token=token_a,
        expected=404,
        payload={"name": f"Cross parent {nonce}", "status": "active", "summary": None, "parent_id": project_b["id"]},
    )
    request_json(
        "PATCH",
        f"/v1/projects/{project_b['id']}",
        token=token_a,
        expected=404,
        payload={"summary": "must not mutate"},
    )

    task_a = request_json(
        "POST",
        "/v1/tasks",
        token=token_a,
        expected=201,
        payload={
            "project_id": project_a["id"],
            "title": f"Human task A {nonce}",
            "description": "owned by A",
            "owner_type": "user",
            "owner_ref": USER_A,
            "authority_ceiling": 2,
            "budget_usd": "1.00",
            "input": {},
        },
    )
    task_b = request_json(
        "POST",
        "/v1/tasks",
        token=token_b,
        expected=201,
        payload={
            "project_id": project_b["id"],
            "title": f"Human task B {nonce}",
            "description": "owned by B",
            "owner_type": "user",
            "owner_ref": USER_B,
            "authority_ceiling": 2,
            "budget_usd": "1.00",
            "input": {},
        },
    )
    request_json(
        "POST",
        "/v1/tasks",
        token=token_a,
        expected=404,
        payload={"project_id": project_b["id"], "title": "Must not attach", "input": {}},
    )

    tasks_a = request_json("GET", "/v1/tasks", token=token_a)
    tasks_b = request_json("GET", "/v1/tasks", token=token_b)
    assert task_a["id"] in ids(tasks_a) and task_b["id"] not in ids(tasks_a), tasks_a
    assert task_b["id"] in ids(tasks_b) and task_a["id"] not in ids(tasks_b), tasks_b
    request_json("GET", f"/v1/tasks/{task_b['id']}", token=token_a, expected=404)
    request_json("GET", f"/v1/tasks/{task_a['id']}", token=token_b, expected=404)

    # Planning/Today are user work projections, not global task indexes.
    request_json(
        "PATCH",
        f"/v1/tasks/{task_a['id']}/planning",
        token=token_a,
        payload={"priority": 4},
    )
    request_json(
        "PATCH",
        f"/v1/tasks/{task_b['id']}/planning",
        token=token_b,
        payload={"priority": 4},
    )
    request_json(
        "PATCH",
        f"/v1/tasks/{task_b['id']}/planning",
        token=token_a,
        expected=404,
        payload={"priority": 0},
    )
    planning_a = request_json("GET", "/v1/planning/tasks", token=token_a)
    planning_b = request_json("GET", "/v1/planning/tasks", token=token_b)
    assert task_a["id"] in ids(planning_a) and task_b["id"] not in ids(planning_a), planning_a
    assert task_b["id"] in ids(planning_b) and task_a["id"] not in ids(planning_b), planning_b
    today_a = request_json("GET", "/v1/today?timezone_offset_minutes=0", token=token_a)
    today_b = request_json("GET", "/v1/today?timezone_offset_minutes=0", token=token_b)
    assert task_a["id"] in grouped_today_ids(today_a) and task_b["id"] not in grouped_today_ids(today_a), today_a
    assert task_b["id"] in grouped_today_ids(today_b) and task_a["id"] not in grouped_today_ids(today_b), today_b

    # Capability tasks share the Task table but their Agents read model must still be tenant-scoped.
    agent_a = request_json(
        "POST",
        "/v1/tasks",
        token=token_a,
        expected=201,
        payload={
            "project_id": project_a["id"],
            "title": f"Agent A {nonce}",
            "authority_ceiling": 1,
            "budget_usd": "0",
            "input": {"capability": "fixture.ownership", "authority_level": 1},
        },
    )
    agent_b = request_json(
        "POST",
        "/v1/tasks",
        token=token_b,
        expected=201,
        payload={
            "project_id": project_b["id"],
            "title": f"Agent B {nonce}",
            "authority_ceiling": 1,
            "budget_usd": "0",
            "input": {"capability": "fixture.ownership", "authority_level": 1},
        },
    )
    agents_a = request_json("GET", "/v1/operations/agents", token=token_a)
    agents_b = request_json("GET", "/v1/operations/agents", token=token_b)
    assert agent_a["id"] in ids(agents_a) and agent_b["id"] not in ids(agents_a), agents_a
    assert agent_b["id"] in ids(agents_b) and agent_a["id"] not in ids(agents_b), agents_b

    # Approvals and budgets derive ownership from their Task -> Project chain.
    approval_a = request_json(
        "POST",
        "/v1/approval-requests",
        token=token_a,
        expected=201,
        payload={
            "task_id": task_a["id"],
            "workflow_execution_id": None,
            "action": f"ownership.approve.{nonce}",
            "resource_type": "fixture",
            "resource_id": nonce,
            "authority_level": 2,
            "reason": "ownership proof",
            "scope": {"fixture": nonce},
        },
    )
    request_json(
        "POST",
        "/v1/approval-requests",
        token=token_b,
        expected=404,
        payload={
            "task_id": task_a["id"],
            "workflow_execution_id": None,
            "action": "must.not.create",
            "resource_type": "fixture",
            "resource_id": nonce,
            "authority_level": 1,
            "reason": "foreign task",
            "scope": {},
        },
    )
    approvals_a = request_json("GET", "/v1/approval-requests", token=token_a)
    approvals_b = request_json("GET", "/v1/approval-requests", token=token_b)
    assert approval_a["id"] in ids(approvals_a), approvals_a
    assert approval_a["id"] not in ids(approvals_b), approvals_b
    request_json(
        "POST",
        f"/v1/approval-requests/{approval_a['id']}/decision",
        token=token_b,
        expected=404,
        payload={"decision": "approved", "note": "must not decide"},
    )
    request_json("GET", f"/v1/tasks/{task_a['id']}/budget", token=token_b, expected=404)

    # Explicit graph relationships cannot bridge tenants.
    relationship = request_json(
        "POST",
        "/v1/relationships",
        token=token_a,
        expected=201,
        payload={
            "source_type": "task",
            "source_id": task_a["id"],
            "relation_type": "fixture_relates_to",
            "target_type": "project",
            "target_id": project_a["id"],
            "metadata": {"explanation": "same owner fixture"},
        },
    )
    assert relationship["id"], relationship
    request_json(
        "POST",
        "/v1/relationships",
        token=token_a,
        expected=404,
        payload={
            "source_type": "task",
            "source_id": task_a["id"],
            "relation_type": "must_not_cross",
            "target_type": "project",
            "target_id": project_b["id"],
            "metadata": {},
        },
    )

    # Home, neighborhood, search and natural-language spatial navigation are all the same tenant boundary.
    graph_a = request_json("GET", "/v1/graph/home?max_nodes=80", token=token_a)
    graph_b = request_json("GET", "/v1/graph/home?max_nodes=80", token=token_b)
    graph_ids_a = graph_node_ids(graph_a)
    graph_ids_b = graph_node_ids(graph_b)
    assert project_a["id"] in graph_ids_a and project_b["id"] not in graph_ids_a, graph_a
    assert project_b["id"] in graph_ids_b and project_a["id"] not in graph_ids_b, graph_b
    assert task_a["id"] in graph_ids_a and task_b["id"] not in graph_ids_a, graph_a
    assert task_b["id"] in graph_ids_b and task_a["id"] not in graph_ids_b, graph_b

    request_json(
        "GET",
        f"/v1/graph/neighborhood/project/{project_b['id']}?depth=1&max_nodes=32",
        token=token_a,
        expected=404,
    )
    search_a_for_b = request_json(
        "GET",
        f"/v1/graph/search?q={urllib.parse.quote(project_name_b)}&limit=20",
        token=token_a,
    )
    assert project_b["id"] not in graph_node_ids(search_a_for_b), search_a_for_b
    directive_a_for_b = request_json(
        "POST",
        "/v1/graph/directives/resolve",
        token=token_a,
        payload={"text": f"Montre-moi le projet {project_name_b}"},
    )
    assert directive_a_for_b["outcome"] == "not_found", directive_a_for_b

    architecture = request_json("GET", "/v1/system/architecture", token=token_a)
    assert architecture.get("domain_ownership") == "project-root-keycloak-subject-with-explicit-polymorphic-ownership", architecture

    print(
        "KAIRO two-user Project/Task/Planning/Agents/Approvals/Relationships/Graph ownership proof passed at",
        datetime.now(UTC).isoformat(),
    )


if __name__ == "__main__":
    main()
