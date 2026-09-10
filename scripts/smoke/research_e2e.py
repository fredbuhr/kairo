#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CORE = "http://localhost:8000"
MODEL_BASE = "http://localhost:4010"
INTERNAL_TOKEN = os.getenv("KAIRO_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")
INTERNAL = {"X-Kairo-Internal-Token": INTERNAL_TOKEN}


def request_url(
    base: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            raw = response.read().decode()
            body = json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode()
        body = json.loads(raw) if raw else None
    if status != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {body}")
    return body


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> Any:
    return request_url(
        CORE, method, path, payload=payload, expected=expected, headers=headers
    )


def wait_ready() -> None:
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            if request("GET", "/health/ready")["status"] == "ready":
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Core did not become ready")


def wait_model_fixture() -> None:
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            stats = request_url(MODEL_BASE, "GET", "/stats")
            if stats == {"calls": 0, "stages": []}:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Deterministic Research model fixture did not become ready")


def wait_research(task_id: str) -> dict[str, Any]:
    deadline = time.time() + 120
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        last = request("GET", f"/v1/research/runs/{task_id}")
        if last["status"] == "completed":
            return last
        if last["status"] == "failed" or last.get("execution_status") == "failed":
            raise AssertionError(f"Research failed: {last}")
        time.sleep(0.5)
    raise TimeoutError(f"Research did not complete: {last}")


def main() -> None:
    wait_ready()
    wait_model_fixture()

    project = request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "Research E2E fixture", "status": "active"},
    )
    server = request(
        "POST",
        "/v1/tool-servers",
        expected=201,
        payload={
            "key": "research-fixture",
            "namespace": "fixture",
            "title": "Research fixture MCP",
            "endpoint_url": "http://fake-research-mcp:8766/mcp",
        },
    )
    request(
        "POST",
        f"/internal/v1/tool-servers/{server['id']}/catalog",
        headers=INTERNAL,
        payload={
            "tools": [
                {
                    "name": "search",
                    "title": "Fixture search",
                    "description": "Return one deterministic read-only evidence record.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "minLength": 2, "maxLength": 500}
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                    "output_schema": None,
                    "annotations": {"readOnlyHint": True, "openWorldHint": True},
                }
            ]
        },
    )
    request(
        "PATCH",
        f"/v1/tools/{urllib.parse.quote('fixture.search', safe='')}/policy",
        payload={
            "enabled": True,
            "authority_level": 1,
            "estimated_cost_usd": "0",
            "risk_class": "read",
            "retry_policy": "safe_retry",
        },
    )

    started = request(
        "POST",
        "/v1/research/runs",
        expected=202,
        payload={
            "project_id": project["id"],
            "query": "What does the fixture say about KAIRO research provenance?",
            "max_tool_calls": 1,
            "allowed_tool_keys": ["fixture.search"],
            "model_alias": "local-fast",
            "estimated_model_cost_usd": "0.01",
        },
    )
    result = wait_research(started["task_id"])

    assert result["status"] == "completed", result
    assert result["execution_status"] == "completed", result
    assert result["artifact_id"], result
    assert result["workflow_execution_id"] == started["workflow_execution_id"], result
    assert result["tool_call_count"] == 1, result
    assert len(result["tool_results"]) == 1, result
    assert result["tool_results"][0]["tool_key"] == "fixture.search", result
    assert result["evidence"] == [
        {
            "evidence_id": "E1",
            "slot": 0,
            "tool_key": "fixture.search",
            "invocation_id": result["tool_results"][0]["invocation_id"],
        }
    ], result
    assert result["synthesis"]["claims"][0]["evidence_ids"] == ["E1"], result
    assert "canonical tool invocations" in result["answer"], result
    assert result["planner_model_alias"] == "local-fast", result
    assert result["synthesis_model_alias"] == "local-fast", result

    stats = request_url(MODEL_BASE, "GET", "/stats")
    assert stats == {"calls": 2, "stages": ["plan", "synthesis"]}, stats

    print(
        "PASS: autonomous Research runs plan -> canonical MCP child task -> grounded synthesis -> "
        "one canonical result with E1 provenance and exactly two deterministic model stages"
    )


if __name__ == "__main__":
    main()
