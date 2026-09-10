#!/usr/bin/env python3
"""End-to-end proof that Research survives a real Worker SIGKILL without duplicate external work."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable

CORE = "http://localhost:8000"
MODEL_FIXTURE = "http://localhost:14000"
MCP_METRICS = "http://localhost:18766"
INTERNAL_TOKEN = os.getenv("KAIRO_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")
INTERNAL = {"X-Kairo-Internal-Token": INTERNAL_TOKEN}
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.research-crash.yaml"]


def request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
    if status != expected:
        raise AssertionError(f"{method} {url}: expected {expected}, got {status}: {body}")
    return body


def core_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> Any:
    return request(method, CORE + path, payload=payload, expected=expected, headers=headers)


def wait_until(label: str, predicate: Callable[[], Any], *, timeout: float, interval: float = 0.1) -> Any:
    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except Exception as exc:  # noqa: BLE001 - diagnostics are surfaced on timeout
            last = exc
        time.sleep(interval)
    raise RuntimeError(f"Timed out waiting for {label}; last observation: {last!r}")


def wait_core_ready() -> None:
    wait_until(
        "KAIRO Core readiness",
        lambda: core_request("GET", "/health/ready").get("status") == "ready",
        timeout=90,
        interval=1,
    )


def model_metrics() -> dict[str, int]:
    return request("GET", MODEL_FIXTURE + "/metrics")


def mcp_metrics() -> dict[str, Any]:
    return request("GET", MCP_METRICS + "/metrics")


def invocation_result(invocation_id: uuid.UUID) -> dict[str, Any] | None:
    try:
        return core_request(
            "GET",
            f"/internal/v1/research/tool-invocations/{invocation_id}",
            headers=INTERNAL,
        )
    except AssertionError as exc:
        if "got 404" in str(exc):
            return None
        raise


def postgres_scalar(sql: str) -> str:
    command = [
        *COMPOSE,
        "exec",
        "-T",
        "postgres",
        "sh",
        "-lc",
        f'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc {shlex.quote(sql)}',
    ]
    return subprocess.check_output(command, text=True).strip()


def main() -> None:
    wait_core_ready()
    wait_until("fake model fixture", lambda: model_metrics() == {"planning": 0, "synthesis": 0, "unexpected": 0}, timeout=30)
    wait_until("fake MCP fixture", lambda: mcp_metrics().get("calls") == 0, timeout=30)

    project = core_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "Research crash replay", "status": "active"},
    )
    server = core_request(
        "POST",
        "/v1/tool-servers",
        expected=201,
        payload={
            "key": "research-crash-fixture",
            "namespace": "crash",
            "title": "Research crash fixture",
            "endpoint_url": "http://fake-research-mcp:8765/mcp",
        },
    )
    core_request(
        "POST",
        f"/internal/v1/tool-servers/{server['id']}/catalog",
        headers=INTERNAL,
        payload={
            "tools": [
                {
                    "name": "search",
                    "title": "Deterministic crash-replay search",
                    "description": "One read-only deterministic evidence result.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 500}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                    "annotations": {
                        "readOnlyHint": True,
                        "destructiveHint": False,
                        "idempotentHint": True,
                        "openWorldHint": False,
                    },
                }
            ]
        },
    )
    core_request(
        "PATCH",
        f"/v1/tools/{urllib.parse.quote('crash.search', safe='')}/policy",
        payload={
            "enabled": True,
            "authority_level": 1,
            "estimated_cost_usd": "0",
            "risk_class": "read",
            "retry_policy": "safe_retry",
        },
    )

    started = core_request(
        "POST",
        "/v1/research/runs",
        expected=202,
        payload={
            "project_id": project["id"],
            "query": "Prove that the Research Worker crash path preserves canonical evidence",
            "max_tool_calls": 1,
            "allowed_tool_keys": ["crash.search"],
            "model_alias": "local-fast",
            "estimated_model_cost_usd": "0.01",
        },
    )
    task_id = uuid.UUID(started["task_id"])
    invocation_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"kairo:research:{task_id}:slot:0:crash.search",
    )

    wait_until(
        "one planner call",
        lambda: model_metrics() if model_metrics().get("planning") == 1 else None,
        timeout=30,
    )
    wait_until(
        "one blocked MCP call",
        lambda: mcp_metrics() if mcp_metrics().get("calls") == 1 else None,
        timeout=30,
    )

    # Give the parent activity enough time to observe the child as running and emit at least one
    # replay-preserving `tool-wait` heartbeat. Releasing immediately after the call arrives would
    # make the crash window unnecessarily race-prone.
    time.sleep(1.15)
    request("POST", MCP_METRICS + "/release", payload={})

    completed_invocation = wait_until(
        "canonical child ToolInvocation completion",
        lambda: (
            result
            if (result := invocation_result(invocation_id)) is not None
            and result.get("status") == "completed"
            else None
        ),
        timeout=30,
        interval=0.02,
    )
    assert completed_invocation["invocation_id"] == str(invocation_id), completed_invocation
    assert mcp_metrics()["calls"] == 1, mcp_metrics()

    before_kill = core_request("GET", f"/v1/research/runs/{task_id}")
    if before_kill.get("artifact_id") is not None:
        raise AssertionError("Research completed before the intended crash window")
    before_model = model_metrics()
    if before_model.get("synthesis") != 0:
        raise AssertionError(f"Synthesis started before the intended crash window: {before_model}")

    print("CRASH CHECKPOINT: child invocation is canonical/completed; sending SIGKILL to kairo-worker", flush=True)
    subprocess.run([*COMPOSE, "kill", "-s", "SIGKILL", "kairo-worker"], check=True)
    time.sleep(1.0)
    subprocess.run([*COMPOSE, "up", "-d", "kairo-worker"], check=True)

    completed = wait_until(
        "Research completion after Worker restart",
        lambda: (
            run
            if (run := core_request("GET", f"/v1/research/runs/{task_id}"))
            .get("status") == "completed"
            and run.get("artifact_id")
            else None
        ),
        timeout=180,
        interval=1.0,
    )

    models = model_metrics()
    tools = mcp_metrics()
    assert models == {"planning": 1, "synthesis": 1, "unexpected": 0}, models
    assert tools["calls"] == 1 and tools["completions"] == 1, tools
    assert completed["execution_status"] == "completed", completed
    assert completed["answer"], completed
    assert completed["synthesis"]["claims"][0]["evidence_ids"] == ["E1"], completed
    assert len(completed["evidence"]) == 1, completed
    assert len(completed["tool_invocations"]) == 1, completed
    assert completed["tool_invocations"][0]["invocation_id"] == str(invocation_id), completed

    artifact_count = int(
        postgres_scalar(
            f"select count(*) from artifacts where task_id='{task_id}'::uuid and kind='autonomous-research';"
        )
    )
    usage_count = int(
        postgres_scalar(
            f"select count(*) from model_usage_records where task_id='{task_id}'::uuid;"
        )
    )
    invocation_count = int(
        postgres_scalar(
            "select count(*) from tool_invocations "
            f"where idempotency_key='research:{task_id}:0:crash.search';"
        )
    )
    assert artifact_count == 1, artifact_count
    assert usage_count == 2, usage_count
    assert invocation_count == 1, invocation_count

    replay_read = core_request("GET", f"/v1/research/runs/{task_id}")
    assert replay_read["artifact_id"] == completed["artifact_id"], (completed, replay_read)

    print(
        "PASS: a real Research Worker SIGKILL after canonical MCP completion resumes from Temporal "
        "heartbeats with exactly one planner provider call, one remote MCP call, one synthesis provider "
        "call, two canonical usage rows and one final research Artifact",
        flush=True,
    )


if __name__ == "__main__":
    main()
