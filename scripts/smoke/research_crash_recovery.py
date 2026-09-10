#!/usr/bin/env python3
"""End-to-end crash/replay proof for autonomous Research.

The Worker is hard-stopped after the canonical planner has completed and while the read-only Web
MCP child is across its external SearXNG boundary. The external read may legitimately be retried
because its outcome is ambiguous; KAIRO must nevertheless preserve one logical ToolInvocation,
replay the accounted planner rather than call it again, synthesize once, and create one Artifact.
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
from typing import Any, Callable

CORE = os.getenv("KAIRO_API_URL", "http://127.0.0.1:8000").rstrip("/")
MODEL_STATS = os.getenv("KAIRO_RESEARCH_MODEL_STATS", "http://127.0.0.1:14000/stats")
SEARCH_STATS = os.getenv("KAIRO_RESEARCH_SEARCH_STATS", "http://127.0.0.1:18082/stats")


def json_request(method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw) if raw else None


def core(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    return json_request(method, CORE + path, payload)


def get_json(url: str) -> Any:
    code, payload = json_request("GET", url)
    if code != 200:
        raise AssertionError((url, code, payload))
    return payload


def wait_for(fetch: Callable[[], Any], predicate: Callable[[Any], bool], timeout: float, label: str) -> Any:
    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = fetch()
            if predicate(last):
                return last
        except Exception as exc:  # services may be transitioning during the crash interval
            last = repr(exc)
        time.sleep(0.5)
    raise AssertionError(f"Timed out waiting for {label}; last={last!r}")


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], check=True)


def main() -> int:
    wait_for(
        lambda: core("GET", "/health/ready")[1],
        lambda value: isinstance(value, dict) and value.get("status") == "ready",
        120,
        "Core readiness",
    )

    suffix = uuid.uuid4().hex[:8]
    code, project = core(
        "POST",
        "/v1/projects",
        {"name": f"Research crash proof {suffix}", "status": "active"},
    )
    assert code == 201, (code, project)

    code, run = core(
        "POST",
        "/v1/research/runs",
        {
            "project_id": project["id"],
            "query": "Prove KAIRO durable research recovery",
            "max_tool_calls": 1,
            "allowed_tool_keys": ["web.search"],
            "model_alias": "local-fast",
            "estimated_model_cost_usd": "0.01",
        },
    )
    assert code == 202, (code, run)
    task_id = run["task_id"]
    print("research workflow started:", run, flush=True)

    # Wait until planning is canonically accounted and the child has crossed the external read
    # boundary. Stopping at this point creates a real ambiguous read-only tool outcome.
    wait_for(
        lambda: get_json(MODEL_STATS),
        lambda value: value.get("planning") == 1,
        45,
        "single planner call",
    )
    wait_for(
        lambda: get_json(SEARCH_STATS),
        lambda value: value.get("requests", 0) >= 1,
        45,
        "active SearXNG request",
    )

    compose("stop", "-t", "0", "kairo-worker")
    print("hard-stopped kairo-worker during Web tool execution", flush=True)
    time.sleep(3)

    code, interrupted = core("GET", f"/v1/research/runs/{task_id}")
    assert code == 200, (code, interrupted)
    assert interrupted["status"] in {"queued", "running"}, interrupted
    assert interrupted["artifact_id"] is None, interrupted

    compose("start", "kairo-worker")
    print("restarted kairo-worker; waiting for Temporal recovery", flush=True)

    completed = wait_for(
        lambda: core("GET", f"/v1/research/runs/{task_id}")[1],
        lambda value: isinstance(value, dict) and value.get("status") == "completed",
        210,
        "Research completion after Worker restart",
    )
    assert completed["execution_status"] == "completed", completed
    assert completed["artifact_id"], completed
    assert completed["answer"] == "The recovered research run completed from the supplied Web evidence.", completed
    assert completed["tool_call_count"] == 1, completed
    assert len(completed["tool_invocations"]) == 1, completed
    invocation = completed["tool_invocations"][0]
    assert invocation["tool_key"] == "web.search", invocation
    assert invocation["invocation_id"], invocation
    assert completed["evidence"][0]["invocation_id"] == invocation["invocation_id"], completed
    assert completed["synthesis"]["claims"][0]["evidence_ids"] == ["E1"], completed

    model_stats = get_json(MODEL_STATS)
    assert model_stats["planning"] == 1, model_stats
    assert model_stats["synthesis"] == 1, model_stats
    assert model_stats["total"] == 2, model_stats
    assert len(set(model_stats["call_ids"])) == 2, model_stats

    # A safe-retry read may have crossed the network twice after an ambiguous crash. This is
    # expected; the canonical invocation and final Artifact must still each exist exactly once.
    search_stats = get_json(SEARCH_STATS)
    assert search_stats["requests"] >= 1, search_stats

    code, artifacts = core("GET", f"/v1/tasks/{task_id}/artifacts")
    assert code == 200, (code, artifacts)
    assert len(artifacts) == 1, artifacts
    assert artifacts[0]["id"] == completed["artifact_id"], artifacts
    assert artifacts[0]["workflow_execution_id"] == completed["workflow_execution_id"], artifacts

    code, rerun = core("POST", f"/v1/tasks/{task_id}/run")
    assert code == 409, (code, rerun)

    print(
        "PASS: Research survived a hard Worker stop with one canonical tool invocation, one planner "
        "call, one synthesis call and one final Artifact",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"RESEARCH CRASH RECOVERY FAILED: {exc!r}", file=sys.stderr)
        raise
