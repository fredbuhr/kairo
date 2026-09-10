#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import time
import urllib.parse
from decimal import Decimal
from typing import Any

from research_e2e import INTERNAL, MODEL_BASE, request, request_url, wait_model_fixture, wait_ready, wait_research


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], check=True)


def wait_planner_accounted(task_id: str) -> dict[str, Any]:
    """Wait until Core has the planner's provider usage, which implies a result checkpoint exists."""

    deadline = time.monotonic() + 45
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last = request("GET", f"/v1/tasks/{task_id}/budget")
        if Decimal(str(last.get("spent_usd") or "0")) >= Decimal("0.000100"):
            stats = request_url(MODEL_BASE, "GET", "/stats")
            assert stats == {"calls": 1, "stages": ["plan"]}, stats
            return last
        time.sleep(0.2)
    raise TimeoutError(f"Planner usage was not canonically accounted: {last}")


def main() -> None:
    wait_ready()
    wait_model_fixture()

    project = request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "Research crash replay fixture", "status": "active"},
    )
    server = request(
        "POST",
        "/v1/tool-servers",
        expected=201,
        payload={
            "key": "research-crash-fixture",
            "namespace": "crashfixture",
            "title": "Research crash fixture MCP",
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
    tool_key = "crashfixture.search"
    request(
        "PATCH",
        f"/v1/tools/{urllib.parse.quote(tool_key, safe='')}/policy",
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
            "allowed_tool_keys": [tool_key],
            "model_alias": "local-fast",
            "estimated_model_cost_usd": "0.01",
        },
    )
    task_id = started["task_id"]
    accounted = wait_planner_accounted(task_id)
    assert Decimal(str(accounted["spent_usd"])) == Decimal("0.000100"), accounted

    # Hard-stop immediately after the planner result is safe to replay. The delayed read-only MCP
    # fixture keeps synthesis from racing ahead while the crash is injected.
    compose("stop", "-t", "0", "kairo-worker")
    time.sleep(3)

    during_stop = request("GET", f"/v1/research/runs/{task_id}")
    assert during_stop["status"] == "running", during_stop
    stats_during_stop = request_url(MODEL_BASE, "GET", "/stats")
    assert stats_during_stop == {"calls": 1, "stages": ["plan"]}, stats_during_stop

    compose("start", "kairo-worker")
    result = wait_research(task_id, timeout=210)

    assert result["status"] == "completed", result
    assert result["execution_status"] == "completed", result
    assert result["workflow_execution_id"] == started["workflow_execution_id"], result
    assert result["tool_call_count"] == 1, result
    assert len(result["tool_results"]) == 1, result
    assert result["tool_results"][0]["tool_key"] == tool_key, result
    assert result["evidence"][0]["evidence_id"] == "E1", result
    assert result["evidence"][0]["invocation_id"] == result["tool_results"][0]["invocation_id"], result
    assert result["synthesis"]["claims"][0]["evidence_ids"] == ["E1"], result

    final_stats = request_url(MODEL_BASE, "GET", "/stats")
    assert final_stats == {"calls": 2, "stages": ["plan", "synthesis"]}, final_stats

    budget = request("GET", f"/v1/tasks/{task_id}/budget")
    assert Decimal(str(budget["spent_usd"])) == Decimal("0.000200"), budget

    artifacts = request("GET", f"/v1/tasks/{task_id}/artifacts")
    assert len(artifacts) == 1, artifacts
    assert artifacts[0]["id"] == result["artifact_id"], (artifacts, result)

    print(
        "PASS: Research survives a hard Worker stop after accounted planning, reuses the planner "
        "checkpoint, keeps one canonical tool result and produces one Artifact with only two model calls"
    )


if __name__ == "__main__":
    main()
