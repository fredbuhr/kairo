#!/usr/bin/env python3
"""End-to-end proof of KAIRO's canonical conversational command kernel."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

CORE = "http://localhost:8000"
INTERNAL = {"X-Kairo-Internal-Token": "CHANGE_ME_INTERNAL_TOKEN"}


def json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers=request_headers,
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
    research = next(item for item in capabilities if item["key"] == "research.autonomous")
    semantic = next(item for item in capabilities if item["key"] == "assistant.route.semantic")
    assert news["runtime"] == "temporal", news
    assert news["authority_level"] == 1, news
    assert news["metadata"]["routable"] is True, news
    assert research["version"] == 2, research
    assert research["metadata"]["routable"] is True, research
    assert research["input_schema"]["additionalProperties"] is False, research
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

    # The rich News Artifact remains authoritative, while its summary is projected once into the
    # canonical Conversation as the assistant's compact answer.
    completion_payload = {
        "kind": "news-brief",
        "title": "Paris news fixture",
        "content": {
            "query": routed["parameters"]["query"],
            "mode": "local",
            "summary": "Paris dispose aujourd’hui d’un briefing local déterministe de smoke test.",
            "sources": [],
        },
    }
    _, completed = json_request(
        "POST",
        f"/internal/v1/executions/{routed['workflow_id']}/complete",
        headers=INTERNAL,
        payload=completion_payload,
    )
    artifact_id = completed["artifact"]["id"]
    assert completed["execution_status"] == "completed", completed

    _, messages = json_request("GET", f"/v1/conversations/{conversation_id}/messages")
    assert len(messages) == 2, messages
    assert [message["role"] for message in messages] == ["user", "assistant"], messages
    news_answer = messages[1]
    assert news_answer["content"] == completion_payload["content"]["summary"], news_answer
    assert news_answer["metadata_json"]["kind"] == "capability-result", news_answer
    assert news_answer["metadata_json"]["capability"] == "news.brief", news_answer
    assert news_answer["metadata_json"]["artifact_id"] == artifact_id, news_answer

    # Completion replay cannot duplicate the projected assistant answer.
    _, completed_replay = json_request(
        "POST",
        f"/internal/v1/executions/{routed['workflow_id']}/complete",
        headers=INTERNAL,
        payload=completion_payload,
    )
    assert completed_replay["artifact"]["id"] == artifact_id, completed_replay
    _, replay_messages = json_request("GET", f"/v1/conversations/{conversation_id}/messages")
    assert len(replay_messages) == 2, replay_messages
    assert replay_messages[1]["id"] == news_answer["id"], replay_messages

    _, completed_command = json_request("GET", f"/v1/commands/{command_id}")
    assert completed_command["status"] == "accepted", completed_command
    assert completed_command["result_json"]["execution_status"] == "completed", completed_command
    assert completed_command["result_json"]["artifact_id"] == artifact_id, completed_command
    assert completed_command["result_json"]["assistant_message_id"] == news_answer["id"], completed_command

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
    assert Decimal(str(routing_task["budget_usd"])) == Decimal("0.02"), routing_task
    assert routing_task["authority_ceiling"] == 1, routing_task

    # A terminal routing-workflow failure must also terminalize the canonical Command. Otherwise
    # clients would poll a permanently stuck `routing` state even though Temporal already failed.
    json_request(
        "POST",
        f"/internal/v1/executions/{pending['routing_workflow_id']}/fail",
        payload={"error": "forced semantic routing failure for smoke proof"},
        headers=INTERNAL,
    )
    _, failed_command = json_request("GET", f"/v1/commands/{pending['command_id']}")
    assert failed_command["status"] == "failed", failed_command
    assert failed_command["route_reason"] == "semantic.execution-failed", failed_command
    assert "semantic_error" in failed_command["result_json"], failed_command

    # The second user command is present, but a semantic routing infrastructure failure is not a
    # capability result and therefore does not masquerade as an assistant answer.
    _, messages = json_request("GET", f"/v1/conversations/{conversation_id}/messages")
    assert len(messages) == 3, messages
    assert [message["role"] for message in messages] == ["user", "assistant", "user"], messages

    print(
        "COMMAND KERNEL INTEGRATION PASS: registered capability boundaries, canonical user/assistant "
        "conversation state, deterministic News handoff/result projection, durable semantic fallback and "
        "terminal routing failure propagation are proven."
    )


if __name__ == "__main__":
    main()
