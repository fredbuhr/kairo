#!/usr/bin/env python3
"""End-to-end proof for durable PydanticAI semantic capability routing."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from typing import Any

CORE = "http://localhost:8000"
COMMAND_TEXT = "Que s'est-il passé à Paris ce matin ?"


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
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"KAIRO Core did not become ready: {last_error}")


def wait_command(command_id: str, timeout: float = 90) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        _, last = json_request("GET", f"/v1/commands/{command_id}")
        if last["status"] in {"accepted", "unsupported", "failed"}:
            return last
        time.sleep(0.5)
    raise AssertionError(f"Semantic command did not settle: {last}")


def wait_task(task_id: str, terminal: set[str], timeout: float = 90) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        _, last = json_request("GET", f"/v1/tasks/{task_id}")
        if last["status"] in terminal:
            return last
        time.sleep(0.5)
    raise AssertionError(f"Task {task_id} did not reach {terminal}: {last}")


def main() -> None:
    wait_ready()

    _, initial = json_request(
        "POST",
        "/v1/assistant/commands",
        expected=202,
        payload={"text": COMMAND_TEXT, "locale": "fr-FR", "output": "auto"},
    )
    assert initial["routing"] == "semantic", initial
    assert initial["status"] == "routing", initial
    assert initial["capability"] is None, initial
    assert initial["route_reason"] == "semantic.pending", initial
    command_id = initial["command_id"]
    routing_task_id = initial["routing_task_id"]

    expected_routing_task = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:semantic-route:{command_id}:v1")
    )
    assert routing_task_id == expected_routing_task, initial

    _, routing_task = json_request("GET", f"/v1/tasks/{routing_task_id}")
    assert routing_task["input"]["capability"] == "assistant.route.semantic", routing_task
    assert routing_task["input"]["text"] == COMMAND_TEXT, routing_task
    assert routing_task["input"]["routable_capabilities"][0]["key"] == "news.brief", routing_task
    assert Decimal(str(routing_task["budget_usd"])) == Decimal("0.02"), routing_task

    command = wait_command(command_id)
    assert command["status"] == "accepted", command
    assert command["capability_key"] == "news.brief", command
    assert command["route_reason"] == "semantic.model", command
    assert float(command["confidence"]) == 0.93, command
    assert command["parameters_json"]["mode"] == "local", command
    assert command["parameters_json"]["location"] == "Paris", command

    expected_final_task = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:command:{command_id}:news.brief:v1")
    )
    assert command["task_id"] == expected_final_task, command
    assert command["workflow_execution_id"], command

    _, final_task = json_request("GET", f"/v1/tasks/{expected_final_task}")
    assert final_task["input"]["capability"] == "news.brief", final_task
    assert final_task["input"]["command_id"] == command_id, final_task
    assert final_task["input"]["location"] == "Paris", final_task

    routing_task = wait_task(routing_task_id, {"completed"})
    assert routing_task["status"] == "completed", routing_task
    _, artifacts = json_request("GET", f"/v1/tasks/{routing_task_id}/artifacts")
    semantic_artifact = next(item for item in artifacts if item["kind"] == "semantic-route")
    content = semantic_artifact["content"]
    assert content["model_alias"] == "local-fast", content
    assert content["proposal"]["capability"] == "news.brief", content
    assert content["proposal"]["confidence"] == 0.93, content
    assert content["applied"]["status"] == "accepted", content
    assert content["applied"]["task_id"] == expected_final_task, content

    # The same semantic proposal is replay-safe at Core: it returns the existing final Task rather
    # than producing another capability invocation.
    replay_request = urllib.request.Request(
        CORE + f"/internal/v1/assistant/commands/{command_id}/semantic-route",
        data=json.dumps(content["proposal"]).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Kairo-Internal-Token": "CHANGE_ME_INTERNAL_TOKEN",
        },
    )
    with urllib.request.urlopen(replay_request, timeout=10) as response:
        replay = json.loads(response.read().decode("utf-8"))
    assert replay["status"] == "accepted", replay
    assert replay["task_id"] == expected_final_task, replay

    print(
        "SEMANTIC COMMAND INTEGRATION PASS: ambiguous input is durably routed through PydanticAI and "
        "the accounted model gateway, Core validates the registered capability, and replay reuses the "
        "same deterministic final Task."
    )


if __name__ == "__main__":
    main()
