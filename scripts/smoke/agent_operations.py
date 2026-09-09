#!/usr/bin/env python3
"""End-to-end proof for KAIRO's capability-execution / human-work boundary."""

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

    _, project = json_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={
            "name": "Agent Operations Smoke Project",
            "status": "active",
            "summary": "Canonical execution-task boundary proof.",
        },
    )
    _, execution_task = json_request(
        "POST",
        "/v1/tasks",
        expected=201,
        payload={
            "project_id": project["id"],
            "title": "Fixture durable agent execution",
            "description": "Must appear in Agents and stay out of human Today/Gantt.",
            "owner_type": "system",
            "owner_ref": "agent-operations-smoke",
            "authority_ceiling": 2,
            "budget_usd": 0.25,
            "input": {
                "capability": "fixture.agent",
                "query": "prove agent operations",
            },
        },
    )

    _, planning = json_request("GET", "/v1/planning/tasks?include_closed=true")
    assert all(item["id"] != execution_task["id"] for item in planning), planning
    json_request(
        "PATCH",
        f"/v1/tasks/{execution_task['id']}/planning",
        expected=409,
        payload={"priority": 4},
    )

    _, approval = json_request(
        "POST",
        "/v1/approval-requests",
        expected=201,
        payload={
            "task_id": execution_task["id"],
            "requested_by": "fixture-agent",
            "action": "fixture.external.write",
            "resource_type": "fixture-resource",
            "resource_id": "fixture-42",
            "authority_level": 2,
            "reason": "Prove that pending approvals surface in the canonical Agents workspace.",
            "scope": {"fixture": True},
        },
    )

    _, operations = json_request("GET", "/v1/operations/agents?limit=100")
    run = next(item for item in operations if item["task_id"] == execution_task["id"])
    assert run["capability"] == "fixture.agent", run
    assert run["pending_approvals"] == 1, run
    assert float(run["spent_usd"]) == 0, run
    assert abs(float(run["budget_usd"]) - 0.25) < 0.0001, run
    assert run["metadata"]["query"] == "prove agent operations", run

    _, pending = json_request("GET", "/v1/approval-requests?approval_status=pending")
    assert any(item["id"] == approval["id"] for item in pending), pending

    _, decision = json_request(
        "POST",
        f"/v1/approval-requests/{approval['id']}/decision",
        payload={"decision": "approved", "note": "smoke approval"},
    )
    assert decision["status"] == "approved", decision

    _, after = json_request("GET", "/v1/operations/agents?limit=100")
    run_after = next(item for item in after if item["task_id"] == execution_task["id"])
    assert run_after["pending_approvals"] == 0, run_after

    print("KAIRO Agents operations + human-work boundary smoke proof passed")


if __name__ == "__main__":
    main()
