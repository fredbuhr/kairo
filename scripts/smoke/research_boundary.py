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
INTERNAL_TOKEN = os.getenv("KAIRO_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")
INTERNAL = {"X-Kairo-Internal-Token": INTERNAL_TOKEN}


def request(method: str, path: str, *, payload: dict[str, Any] | None = None, expected: int = 200, headers: dict[str, str] | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read().decode())
    if status != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {body}")
    return body


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


def main() -> None:
    wait_ready()
    project = request("POST", "/v1/projects", expected=201, payload={"name": "Research boundary smoke", "status": "active"})
    server = request(
        "POST",
        "/v1/tool-servers",
        expected=201,
        payload={
            "key": "research-smoke",
            "namespace": "researchsmoke",
            "title": "Research smoke tools",
            "endpoint_url": "http://fake-mcp:8765/mcp",
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
                    "title": "Search",
                    "description": "Read-only source discovery",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                    "annotations": {"readOnlyHint": True, "idempotentHint": True},
                },
                {
                    "name": "send",
                    "title": "Send",
                    "description": "Side-effecting tool",
                    "input_schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                        "additionalProperties": False,
                    },
                    "annotations": {},
                },
            ]
        },
    )
    for key, policy in {
        "researchsmoke.search": {"enabled": True, "authority_level": 1, "risk_class": "read", "retry_policy": "safe_retry"},
        "researchsmoke.send": {"enabled": True, "authority_level": 2, "risk_class": "write", "retry_policy": "no_retry"},
    }.items():
        request("PATCH", f"/v1/tools/{urllib.parse.quote(key, safe='')}/policy", payload=policy)

    parent = request(
        "POST",
        "/v1/tasks",
        expected=201,
        payload={
            "project_id": project["id"],
            "title": "Research parent",
            "owner_type": "agent",
            "owner_ref": "kairo.research-agent",
            "authority_ceiling": 1,
            "budget_usd": "0.01",
            "input": {
                "capability": "research.autonomous",
                "query": "Find evidence about KAIRO",
                "max_tool_calls": 2,
                "allowed_tool_keys": [],
                "model_alias": "local-fast",
                "estimated_model_cost_usd": "0.01",
                "authority_level": 1,
                "estimated_cost_usd": "0.01",
            },
        },
    )

    context = request("GET", f"/internal/v1/research/tasks/{parent['id']}/context", headers=INTERNAL)
    keys = {tool["key"] for tool in context["tools"]}
    assert keys == {"researchsmoke.search"}, context

    request(
        "POST",
        f"/internal/v1/research/tasks/{parent['id']}/tool-invocations",
        expected=409,
        headers=INTERNAL,
        payload={"tool_key": "researchsmoke.send", "input": {"message": "no"}, "slot": 0, "rationale": "must be rejected"},
    )

    first = request(
        "POST",
        f"/internal/v1/research/tasks/{parent['id']}/tool-invocations",
        headers=INTERNAL,
        payload={"tool_key": "researchsmoke.search", "input": {"query": "KAIRO"}, "slot": 0, "rationale": "read evidence"},
    )
    replay = request(
        "POST",
        f"/internal/v1/research/tasks/{parent['id']}/tool-invocations",
        headers=INTERNAL,
        payload={"tool_key": "researchsmoke.search", "input": {"query": "KAIRO"}, "slot": 0, "rationale": "same logical call"},
    )
    assert replay["invocation_id"] == first["invocation_id"], (first, replay)
    assert replay["task_id"] == first["task_id"], (first, replay)

    request(
        "POST",
        f"/internal/v1/research/tasks/{parent['id']}/tool-invocations",
        expected=409,
        headers=INTERNAL,
        payload={"tool_key": "researchsmoke.search", "input": {"query": "DIFFERENT"}, "slot": 0, "rationale": "slot rebinding must fail"},
    )
    print("PASS: Core exposes only read/A1 tools and research child slots are deterministic")


if __name__ == "__main__":
    main()
