#!/usr/bin/env python3
"""Block 1 end-to-end durability proof.

Creates canonical state, proves concurrent starts converge on one durable execution, then starts
another Temporal workflow, hard-stops the worker during a heartbeat activity, restarts it and
verifies exactly-once canonical completion.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

BASE_URL = os.environ.get("KAIRO_API_URL", "http://127.0.0.1:8000").rstrip("/")


def request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        payload = json.loads(raw) if raw else None
        return exc.code, payload


def wait_for(path: str, predicate, timeout: float, label: str) -> Any:
    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        try:
            code, last = request("GET", path)
            if code == 200 and predicate(last):
                return last
        except Exception as exc:  # service may be restarting
            last = repr(exc)
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for {label}; last={last!r}")


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], check=True)


def main() -> int:
    ready = wait_for(
        "/health/ready",
        lambda payload: payload.get("status") == "ready",
        120,
        "KAIRO Core readiness",
    )
    print("ready:", ready)

    suffix = uuid.uuid4().hex[:8]
    code, project = request(
        "POST",
        "/v1/projects",
        {"name": f"Block1 proof {suffix}", "summary": "CI durability proof"},
    )
    assert code == 201, (code, project)

    # Prove two user requests arriving at the same time converge on the same canonical execution
    # and deterministic Temporal Workflow ID instead of creating duplicate work records.
    code, concurrent_task = request(
        "POST",
        "/v1/tasks",
        {
            "project_id": project["id"],
            "title": "Converge concurrent starts",
            "authority_ceiling": 1,
            "input": {"delay_seconds": 4, "proof": f"concurrent-{suffix}"},
        },
    )
    assert code == 201, (code, concurrent_task)

    concurrent_path = f"/v1/tasks/{concurrent_task['id']}/run"
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(request, "POST", concurrent_path) for _ in range(2)]
        concurrent_runs = [future.result(timeout=20) for future in futures]

    assert all(code == 200 for code, _ in concurrent_runs), concurrent_runs
    first_run = concurrent_runs[0][1]
    second_run = concurrent_runs[1][1]
    assert first_run["workflow_execution_id"] == second_run["workflow_execution_id"], concurrent_runs
    assert first_run["workflow_id"] == second_run["workflow_id"], concurrent_runs
    assert any(run[1]["already_started"] for run in concurrent_runs), concurrent_runs

    wait_for(
        f"/v1/tasks/{concurrent_task['id']}",
        lambda payload: payload.get("status") == "completed",
        60,
        "concurrent task completion",
    )
    code, concurrent_artifacts = request(
        "GET", f"/v1/tasks/{concurrent_task['id']}/artifacts"
    )
    assert code == 200, (code, concurrent_artifacts)
    assert len(concurrent_artifacts) == 1, concurrent_artifacts
    print("concurrent starts converged on one execution and one artifact")

    code, task = request(
        "POST",
        "/v1/tasks",
        {
            "project_id": project["id"],
            "title": "Survive hard worker stop",
            "authority_ceiling": 1,
            "input": {"delay_seconds": 12, "proof": suffix},
        },
    )
    assert code == 201, (code, task)

    code, relationship = request(
        "POST",
        "/v1/relationships",
        {
            "source_type": "project",
            "source_id": project["id"],
            "relation_type": "contains",
            "target_type": "task",
            "target_id": task["id"],
            "metadata": {"proof": "block1"},
        },
    )
    assert code == 201, (code, relationship)

    code, run = request("POST", f"/v1/tasks/{task['id']}/run")
    assert code == 200, (code, run)
    print("workflow:", run)

    running = wait_for(
        f"/v1/tasks/{task['id']}",
        lambda payload: payload.get("status") == "running",
        45,
        "task running state",
    )
    print("running before crash:", running["id"])

    # `stop -t 0` forces immediate termination but leaves the container explicitly stopped,
    # preventing the restart policy from hiding the failure interval.
    compose("stop", "-t", "0", "kairo-worker")
    time.sleep(7)

    code, during_stop = request("GET", f"/v1/tasks/{task['id']}")
    assert code == 200, during_stop
    assert during_stop["status"] == "running", during_stop
    print("canonical task remained running while worker was down")

    compose("start", "kairo-worker")

    completed = wait_for(
        f"/v1/tasks/{task['id']}",
        lambda payload: payload.get("status") == "completed",
        90,
        "task completion after worker restart",
    )
    print("completed after restart:", completed["id"])

    code, artifacts = request("GET", f"/v1/tasks/{task['id']}/artifacts")
    assert code == 200, (code, artifacts)
    assert len(artifacts) == 1, artifacts
    assert artifacts[0]["workflow_execution_id"] == run["workflow_execution_id"], artifacts

    code, second_run = request("POST", f"/v1/tasks/{task['id']}/run")
    assert code == 409, (code, second_run)

    outbox = wait_for(
        "/v1/system/outbox",
        lambda payload: payload.get("pending") == 0 and payload.get("published", 0) >= 14,
        45,
        "transactional outbox drain",
    )
    assert outbox["relay_connected"] is True, outbox
    print("outbox:", outbox)
    print(
        "BLOCK 1 SMOKE PASS: concurrent starts converged and durable workflow recovered with one "
        "canonical artifact"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"BLOCK 1 SMOKE FAILED: {exc!r}", file=sys.stderr)
        raise
