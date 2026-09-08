#!/usr/bin/env python3
"""End-to-end proof: Research plan -> MCP child Task -> evidence-bound synthesis -> Artifact."""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any

from mcp import Client

CORE = os.getenv("KAIRO_E2E_CORE", "http://127.0.0.1:8000")
MODEL_FIXTURE = os.getenv("KAIRO_E2E_MODEL", "http://127.0.0.1:4000")
MCP_FIXTURE = os.getenv("KAIRO_E2E_MCP", "http://127.0.0.1:8765")
INTERNAL_TOKEN = os.getenv("KAIRO_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")
INTERNAL = {"X-Kairo-Internal-Token": INTERNAL_TOKEN}


def json_request(
    method: str,
    url_or_path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    url = url_or_path if url_or_path.startswith("http") else CORE + url_or_path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read().decode("utf-8")
            body = json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            body = raw
    if status != expected:
        raise AssertionError(f"{method} {url}: expected {expected}, got {status}: {body}")
    return status, body


def wait_json(url: str, *, timeout_seconds: float = 120.0) -> Any:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            _, body = json_request("GET", url, timeout=5.0)
            return body
        except Exception as exc:  # noqa: BLE001 - smoke proof reports final error
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Endpoint did not become ready: {url}: {last_error}")


def wait_task(task_id: str, *, timeout_seconds: float = 180.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        _, task = json_request("GET", f"/v1/tasks/{task_id}")
        last = task
        if task["status"] == "completed":
            return task
        if task["status"] == "failed":
            raise AssertionError(f"Research task failed: {task}")
        time.sleep(1)
    raise TimeoutError(f"Research task did not finish: {last}")


async def live_fixture_catalog_item() -> dict[str, Any]:
    async with Client(MCP_FIXTURE + "/mcp") as client:
        listing = await client.list_tools()
    matches = [tool for tool in listing.tools if tool.name == "company_facts"]
    assert len(matches) == 1, listing
    dumped = matches[0].model_dump(mode="json", by_alias=True)
    input_schema = dumped.get("inputSchema")
    if input_schema is None:
        input_schema = dumped.get("input_schema")
    output_schema = dumped.get("outputSchema")
    if output_schema is None and "output_schema" in dumped:
        output_schema = dumped.get("output_schema")
    assert isinstance(input_schema, dict), dumped
    assert output_schema is None or isinstance(output_schema, dict), dumped
    return {
        "name": "company_facts",
        "title": "Company facts",
        "description": "Read deterministic company facts without side effects.",
        "input_schema": input_schema,
        "output_schema": output_schema,
        "annotations": {"readOnlyHint": True, "idempotentHint": True},
    }


def main() -> None:
    wait_json(CORE + "/health/ready")
    wait_json(MODEL_FIXTURE + "/health")
    wait_json(MCP_FIXTURE + "/health")

    _, project = json_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "Research E2E", "status": "active"},
    )

    _, server = json_request(
        "POST",
        "/v1/tool-servers",
        expected=201,
        payload={
            "key": "research-fixture-server",
            "namespace": "fixture",
            "title": "Research fixture MCP",
            "endpoint_url": MCP_FIXTURE + "/mcp",
            "transport": "mcp_streamable_http",
        },
    )

    live_tool = asyncio.run(live_fixture_catalog_item())
    _, catalog = json_request(
        "POST",
        f"/internal/v1/tool-servers/{server['id']}/catalog",
        headers=INTERNAL,
        payload={"tools": [live_tool]},
    )
    assert len(catalog) == 1, catalog
    tool = catalog[0]
    assert tool["key"] == "fixture.company_facts", tool
    assert tool["enabled"] is False, tool
    assert tool["risk_class"] == "read", tool
    assert tool["authority_level"] == 1, tool
    assert len(tool["schema_hash"]) == 64, tool

    encoded_key = urllib.parse.quote("fixture.company_facts", safe="")
    _, enabled = json_request(
        "PATCH",
        f"/v1/tools/{encoded_key}/policy",
        payload={
            "enabled": True,
            "authority_level": 1,
            "estimated_cost_usd": "0",
            "risk_class": "read",
            "retry_policy": "safe_retry",
        },
    )
    assert enabled["enabled"] is True, enabled

    _, started = json_request(
        "POST",
        "/v1/research/runs",
        expected=202,
        payload={
            "project_id": project["id"],
            "query": "What are Acme Fixture's revenue and employee count?",
            "max_tool_calls": 1,
            "allowed_tool_keys": ["fixture.company_facts"],
            "model_alias": "local-fast",
            "estimated_model_cost_usd": "0.02",
        },
    )
    task_id = str(started["task_id"])
    task = wait_task(task_id)
    assert task["status"] == "completed", task
    assert Decimal(str(task["budget_usd"])) == Decimal("0.02"), task

    _, artifacts = json_request("GET", f"/v1/tasks/{task_id}/artifacts")
    assert len(artifacts) == 1, artifacts
    artifact = artifacts[0]
    assert artifact["kind"] == "autonomous-research", artifact

    _, public_run = json_request("GET", f"/v1/research/runs/{task_id}")
    assert public_run["task_id"] == task_id, public_run
    assert public_run["project_id"] == project["id"], public_run
    assert public_run["status"] == "completed", public_run
    assert public_run["query"] == "What are Acme Fixture's revenue and employee count?", public_run
    assert public_run["artifact"]["id"] == artifact["id"], public_run

    content = public_run["artifact"]["content"]
    assert content["tool_call_count"] == 1, content
    assert content["model_call_slots"] == ["research-plan-v1", "research-synthesize-v1"], content
    assert content["plan"]["calls"][0]["tool_key"] == "fixture.company_facts", content

    report = content["report"]
    assert "42" in report["answer"] and "120" in report["answer"], report
    assert len(report["findings"]) == 1, report
    evidence_ids = report["findings"][0]["evidence_invocation_ids"]
    assert len(evidence_ids) == 1 and evidence_ids[0], report
    invocation_id = evidence_ids[0]

    tool_results = content["tool_results"]
    assert len(tool_results) == 1, tool_results
    assert tool_results[0]["invocation_id"] == invocation_id, tool_results
    assert tool_results[0]["tool_key"] == "fixture.company_facts", tool_results

    _, invocation = json_request("GET", f"/v1/tool-invocations/{invocation_id}")
    assert invocation["status"] == "completed", invocation
    structured = invocation["result_json"].get("structuredContent") or invocation["result_json"].get(
        "structured_content"
    )
    assert isinstance(structured, dict), invocation
    assert structured["company"] == "Acme Fixture", structured
    assert structured["revenue_eur_m"] == 42, structured
    assert structured["employees"] == 120, structured

    _, budget = json_request("GET", f"/v1/tasks/{task_id}/budget")
    assert Decimal(str(budget["spent_usd"])) == Decimal("0.002"), budget
    assert Decimal(str(budget["remaining_usd"])) == Decimal("0.018"), budget

    _, stats = json_request("GET", MODEL_FIXTURE + "/stats")
    assert stats["call_count"] == 2, stats
    assert len(set(stats["call_ids"])) == 2, stats
    assert all(value and value != "missing-call-id" for value in stats["call_ids"]), stats

    print(
        "PASS: autonomous Research synchronized the live MCP schema, planned one read-only child Task, "
        "revalidated the same contract before execution, synthesized a provenance-checked report, exposed "
        "its public read model and accounted exactly two distinct model-call slots"
    )


if __name__ == "__main__":
    main()
