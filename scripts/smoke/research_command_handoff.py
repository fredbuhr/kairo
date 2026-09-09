#!/usr/bin/env python3
"""Integration proof for deterministic + semantic Command Kernel handoff into Research."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from typing import Any

CORE = "http://127.0.0.1:8000"
INTERNAL_TOKEN = os.getenv("KAIRO_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")
INTERNAL = {"X-Kairo-Internal-Token": INTERNAL_TOKEN}
ASSISTANT_PROJECT_ID = "91d51873-3aa5-4fbc-a6df-cf474239682f"
RESEARCH_CAPABILITY_VERSION = 2


def json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            raw = response.read().decode("utf-8")
            body = json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
        body = json.loads(raw) if raw else None
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
        except Exception as exc:  # noqa: BLE001 - smoke proof reports final error
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"KAIRO Core did not become ready: {last_error}")


def command_task_id(command_id: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"kairo:command:{command_id}:research.autonomous:v{RESEARCH_CAPABILITY_VERSION}",
        )
    )


def assert_core_owned_research_task(
    task: dict[str, Any], *, command_id: str, query: str, max_tool_calls: int
) -> None:
    assert task["id"] == command_task_id(command_id), task
    assert task["project_id"] == ASSISTANT_PROJECT_ID, task
    assert task["input"]["capability"] == "research.autonomous", task
    assert task["input"]["command_id"] == command_id, task
    assert task["input"]["query"] == query, task
    assert task["input"]["max_tool_calls"] == max_tool_calls, task
    assert task["input"]["allowed_tool_keys"] == [], task
    assert task["input"]["model_alias"] == "local-fast", task
    assert Decimal(str(task["input"]["estimated_model_cost_usd"])) == Decimal("0.02"), task
    assert Decimal(str(task["input"]["estimated_cost_usd"])) == Decimal("0.02"), task
    assert task["input"]["policy_scope"] == {
        "capability": "research.autonomous",
        "tool_risk_ceiling": "read",
    }, task
    assert task["authority_ceiling"] == 1, task
    assert Decimal(str(task["budget_usd"])) == Decimal("0.02"), task


def conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
    _, messages = json_request("GET", f"/v1/conversations/{conversation_id}/messages")
    return messages


def main() -> None:
    wait_ready()

    # 1) High-confidence explicit research routes without paying for semantic routing.
    deterministic_text = "Fais une recherche approfondie sur les architectures d'agents durables."
    _, deterministic = json_request(
        "POST",
        "/v1/assistant/commands",
        expected=202,
        payload={"text": deterministic_text, "locale": "fr-FR", "output": "auto"},
    )
    assert deterministic["status"] == "accepted", deterministic
    assert deterministic["routing"] == "deterministic", deterministic
    assert deterministic["capability"] == "research.autonomous", deterministic
    assert deterministic["route_reason"] == "deterministic.research", deterministic
    assert deterministic["parameters"] == {
        "query": deterministic_text,
        "max_tool_calls": 5,
    }, deterministic
    assert deterministic.get("routing_task_id") is None, deterministic
    assert deterministic["task_id"] == command_task_id(deterministic["command_id"]), deterministic

    _, deterministic_task = json_request("GET", f"/v1/tasks/{deterministic['task_id']}")
    assert_core_owned_research_task(
        deterministic_task,
        command_id=deterministic["command_id"],
        query=deterministic_text,
        max_tool_calls=5,
    )
    _, deterministic_command = json_request(
        "GET", f"/v1/commands/{deterministic['command_id']}"
    )
    assert deterministic_command["parameters_json"] == deterministic["parameters"], deterministic_command
    assert "model_alias" not in deterministic_command["parameters_json"], deterministic_command
    assert "estimated_model_cost_usd" not in deterministic_command["parameters_json"], deterministic_command

    # Completion is projected into the canonical Conversation exactly once. The full Artifact remains
    # authoritative; the assistant message is a compact, memory-projectable view of the final answer.
    completion_payload = {
        "kind": "autonomous-research",
        "title": "Research fixture result",
        "content": {
            "query": deterministic_text,
            "report": {
                "answer": "Les workflows durables rendent les opérations longues rejouables et auditables.",
                "findings": [],
                "caveats": ["Résultat synthétique de smoke test."],
            },
            "tool_results": [],
            "tool_call_count": 0,
        },
    }
    _, completed = json_request(
        "POST",
        f"/internal/v1/executions/{deterministic['workflow_id']}/complete",
        headers=INTERNAL,
        payload=completion_payload,
    )
    assert completed["execution_status"] == "completed", completed
    artifact_id = completed["artifact"]["id"]

    messages = conversation_messages(deterministic["conversation_id"])
    assert len(messages) == 2, messages
    assert [message["role"] for message in messages] == ["user", "assistant"], messages
    assistant_message = messages[1]
    assert assistant_message["content"] == completion_payload["content"]["report"]["answer"], messages
    assert assistant_message["metadata_json"]["kind"] == "capability-result", assistant_message
    assert assistant_message["metadata_json"]["command_id"] == deterministic["command_id"], assistant_message
    assert assistant_message["metadata_json"]["task_id"] == deterministic["task_id"], assistant_message
    assert assistant_message["metadata_json"]["artifact_id"] == artifact_id, assistant_message

    # Retrying canonical completion repairs/returns state without duplicating chat history.
    _, completed_replay = json_request(
        "POST",
        f"/internal/v1/executions/{deterministic['workflow_id']}/complete",
        headers=INTERNAL,
        payload=completion_payload,
    )
    assert completed_replay["artifact"]["id"] == artifact_id, completed_replay
    replay_messages = conversation_messages(deterministic["conversation_id"])
    assert len(replay_messages) == 2, replay_messages
    assert replay_messages[1]["id"] == assistant_message["id"], replay_messages

    _, completed_command = json_request("GET", f"/v1/commands/{deterministic['command_id']}")
    assert completed_command["status"] == "accepted", completed_command
    assert completed_command["result_json"]["execution_status"] == "completed", completed_command
    assert completed_command["result_json"]["artifact_id"] == artifact_id, completed_command
    assert completed_command["result_json"]["assistant_message_id"] == assistant_message["id"], completed_command

    # 2) An ambiguous request enters semantic routing. We emulate the bounded router proposal and
    # prove Core creates the final Research Task with authority fields it owns itself.
    semantic_text = "Compare plusieurs sources fiables sur la robustesse des systèmes multi-agents."
    _, pending = json_request(
        "POST",
        "/v1/assistant/commands",
        expected=202,
        payload={"text": semantic_text, "locale": "fr-FR", "output": "auto"},
    )
    assert pending["status"] == "routing", pending
    assert pending["routing"] == "semantic", pending
    assert pending["route_reason"] == "semantic.pending", pending

    proposal = {
        "outcome": "route",
        "capability": "research.autonomous",
        "confidence": 0.94,
        "parameters": {
            "query": semantic_text,
            "max_tool_calls": 2,
        },
        "rationale": "The request asks for evidence comparison rather than a current-news brief.",
    }
    _, applied = json_request(
        "POST",
        f"/internal/v1/assistant/commands/{pending['command_id']}/semantic-route",
        headers=INTERNAL,
        payload=proposal,
    )
    assert applied["status"] == "accepted", applied
    assert applied["capability"] == "research.autonomous", applied
    assert applied["task_id"] == command_task_id(pending["command_id"]), applied

    _, semantic_task = json_request("GET", f"/v1/tasks/{applied['task_id']}")
    assert_core_owned_research_task(
        semantic_task,
        command_id=pending["command_id"],
        query=semantic_text,
        max_tool_calls=2,
    )
    _, semantic_command = json_request("GET", f"/v1/commands/{pending['command_id']}")
    assert semantic_command["status"] == "accepted", semantic_command
    assert semantic_command["capability_key"] == "research.autonomous", semantic_command
    assert semantic_command["parameters_json"] == proposal["parameters"], semantic_command

    # Retrying the semantic apply endpoint is a pure read of the already-authoritative handoff.
    _, replay = json_request(
        "POST",
        f"/internal/v1/assistant/commands/{pending['command_id']}/semantic-route",
        headers=INTERNAL,
        payload=proposal,
    )
    assert replay["status"] == "accepted", replay
    assert replay["task_id"] == applied["task_id"], replay
    assert replay["workflow_execution_id"] == applied["workflow_execution_id"], replay
    assert replay["workflow_id"] == applied["workflow_id"], replay

    # 3) Semantic routing cannot smuggle execution-authority fields into the Research contract.
    authority_text = "Compare des sources sur les architectures de mémoire pour agents."
    _, authority_pending = json_request(
        "POST",
        "/v1/assistant/commands",
        expected=202,
        payload={"text": authority_text, "locale": "fr-FR", "output": "auto"},
    )
    assert authority_pending["status"] == "routing", authority_pending
    malicious = {
        "outcome": "route",
        "capability": "research.autonomous",
        "confidence": 0.95,
        "parameters": {
            "query": authority_text,
            "max_tool_calls": 2,
            "model_alias": "smart",
            "estimated_model_cost_usd": "1.00",
            "allowed_tool_keys": ["dangerous.write"],
        },
        "rationale": "Fixture attempts to widen execution authority.",
    }
    _, rejected = json_request(
        "POST",
        f"/internal/v1/assistant/commands/{authority_pending['command_id']}/semantic-route",
        headers=INTERNAL,
        payload=malicious,
    )
    assert rejected["command_id"] == authority_pending["command_id"], rejected
    assert rejected["status"] == "unsupported", rejected
    assert rejected.get("task_id") is None, rejected
    _, rejected_command = json_request(
        "GET", f"/v1/commands/{authority_pending['command_id']}"
    )
    assert rejected_command["status"] == "unsupported", rejected_command
    assert rejected_command["route_reason"] == "semantic.invalid-parameters", rejected_command
    assert rejected_command["task_id"] is None, rejected_command
    json_request(
        "GET",
        f"/v1/tasks/{command_task_id(authority_pending['command_id'])}",
        expected=404,
    )

    # 4) A terminal capability failure updates the Command and adds one user-safe assistant message.
    failure_text = "Fais une recherche sur les compromis des orchestrateurs durables."
    _, failing = json_request(
        "POST",
        "/v1/assistant/commands",
        expected=202,
        payload={"text": failure_text, "locale": "fr-FR", "output": "auto"},
    )
    assert failing["status"] == "accepted", failing
    _, failed = json_request(
        "POST",
        f"/internal/v1/executions/{failing['workflow_id']}/fail",
        headers=INTERNAL,
        payload={"error": "forced final Research failure for command projection proof"},
    )
    assert failed["status"] == "failed", failed

    _, failed_command = json_request("GET", f"/v1/commands/{failing['command_id']}")
    assert failed_command["status"] == "failed", failed_command
    assert failed_command["result_json"]["execution_status"] == "failed", failed_command
    assert "forced final Research failure" in failed_command["result_json"]["execution_error"], failed_command

    failed_messages = conversation_messages(failing["conversation_id"])
    assert len(failed_messages) == 2, failed_messages
    assert failed_messages[1]["role"] == "assistant", failed_messages
    assert failed_messages[1]["content"] == "KAIRO n’a pas pu terminer cette demande.", failed_messages
    assert failed_messages[1]["metadata_json"]["kind"] == "capability-failure", failed_messages
    assert failed_messages[1]["metadata_json"]["command_id"] == failing["command_id"], failed_messages

    # Failure replay is idempotent and does not leak/duplicate the raw technical error into chat.
    json_request(
        "POST",
        f"/internal/v1/executions/{failing['workflow_id']}/fail",
        headers=INTERNAL,
        payload={"error": "forced final Research failure for command projection proof"},
    )
    failed_replay_messages = conversation_messages(failing["conversation_id"])
    assert len(failed_replay_messages) == 2, failed_replay_messages
    assert failed_replay_messages[1]["id"] == failed_messages[1]["id"], failed_replay_messages

    print(
        "PASS: Command Kernel routes Research v2, rejects authority smuggling, reuses semantic handoffs, "
        "and projects final success/failure exactly once into the canonical Conversation"
    )


if __name__ == "__main__":
    main()
