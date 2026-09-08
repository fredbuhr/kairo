#!/usr/bin/env python3
"""End-to-end proof of KAIRO's canonical conversational command kernel."""

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
    request = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
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
        except Exception as exc:  # noqa: BLE001 - smoke test reports the final readiness failure
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"KAIRO Core did not become ready: {last_error}")


def main() -> None:
    wait_ready()

    _, capabilities = json_request("GET", "/v1/capabilities")
    news = next(item for item in capabilities if item["key"] == "news.brief")
    semantic = next(item for item in capabilities if item["key"] == "assistant.route.semantic")
    assert news["runtime"] == "temporal", news
    assert news["authority_level"] == 1, news
    assert news["metadata"]["routable"] is True, news
    assert semantic["runtime"] == "temporal", semantic
    assert semantic["metadata"]["routable"] is False, semantic
    assert semantic["metadata"]["agent_framework"] == "pydantic-ai", semantic

    _, routed = json_request(
        "POST",
        "/v1/assistant/commands",
        expected=202,
        payload={
            "text": "Quelles sont les nouvelles du jour sur la ville de Paris ?",
            "locale": "fr-FR",
            "output": "auto",
        },
    )
    assert routed["routing"] == "deterministic", routed
    assert routed["status"] == "accepted", routed
    assert routed["capability"] == "news.brief", routed
    assert routed["parameters"]["mode"] == "local", routed
    assert routed["parameters"]["location"] == "Paris", routed
    assert routed["route_reason"] == "deterministic.local-news", routed

    command_id = routed["command_id"]
    conversation_id = routed["conversation_id"]
    task_id = routed["task_id"]

    _, command = json_request("GET", f"/v1/commands/{command_id}")
    assert command["status"] == "accepted", command
    assert command["capability_key"] == "news.brief", command
    assert command["task_id"] == task_id, command
    assert command["workflow_execution_id"] == routed["workflow_execution_id"], command

    _, conversation = json_request("GET", f"/v1/conversations/{conversation_id}")
    assert conversation["status"] == "active", conversation
    assert conversation["locale"] == "fr-FR", conversation

    _, messages = json_request("GET", f"/v1/conversations/{conversation_id}/messages")
    assert len(messages) == 1, messages
    assert messages[0]["role"] == "user", messages
    assert "Paris" in messages[0]["content"], messages

    _, task = json_request("GET", f"/v1/tasks/{task_id}")
    assert task["input"]["capability"] == "news.brief", task
    assert task["input"]["command_id"] == command_id, task

    # With no Worker in this test, an ambiguous command must still be persisted and handed to a
    # durable semantic-routing Task. The command must not be guessed or executed synchronously.
    _, pending = json_request(
        "POST",
        "/v1/assistant/commands",
        expected=202,
        payload={
            "text": "Ouvre mon agenda demain matin.",
            "conversation_id": conversation_id,
            "locale": "fr-FR",
            "output": "auto",
        },
    )
    assert pending["routing"] == "semantic", pending
    assert pending["status"] == "routing", pending
    assert pending["capability"] is None, pending
    assert pending["route_reason"] == "semantic.pending", pending
    assert pending["routing_task_id"], pending
    assert pending["routing_workflow_execution_id"], pending

    _, pending_command = json_request("GET", f"/v1/commands/{pending['command_id']}")
    assert pending_command["status"] == "routing", pending_command
    assert pending_command["capability_key"] is None, pending_command
    assert pending_command["route_reason"] == "semantic.pending", pending_command

    _, routing_task = json_request("GET", f"/v1/tasks/{pending['routing_task_id']}")
    assert routing_task["input"]["capability"] == "assistant.route.semantic", routing_task
    assert routing_task["input"]["command_id"] == pending["command_id"], routing_task
    assert routing_task["budget_usd"] == "0.020000", routing_task
    assert routing_task["authority_ceiling"] == 1, routing_task

    _, messages = json_request("GET", f"/v1/conversations/{conversation_id}/messages")
    assert len(messages) == 2, messages

    print(
        "COMMAND KERNEL INTEGRATION PASS: registered capability boundaries, canonical conversation "
        "state, deterministic Task handoff and durable semantic fallback are proven."
    )


if __name__ == "__main__":
    main()
