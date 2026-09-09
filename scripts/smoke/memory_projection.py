#!/usr/bin/env python3
"""End-to-end proof that KAIRO memory projections are rebuildable and safely purgeable."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

CORE = "http://localhost:8000"
INTERNAL_HEADERS = {"X-Kairo-Internal-Token": "CHANGE_ME_INTERNAL_TOKEN"}


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
        except Exception as exc:  # noqa: BLE001 - smoke test reports the final readiness failure
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"KAIRO Core did not become ready: {last_error}")


def expected_task_id(message_id: str, generation: int) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"kairo:memory:conversation-message:{message_id}:v1:g{generation}",
        )
    )


def wait_for_projection(message_id: str, generation: int) -> list[dict[str, Any]]:
    deadline = time.time() + 90
    last: Any = None
    while time.time() < deadline:
        try:
            _, body = json_request(
                "GET", f"/v1/memory/projections/conversation-messages/{message_id}"
            )
            last = body
            rows = body.get("projectors") or []
            if (
                len(rows) == 2
                and all(int(row["generation"]) == generation for row in rows)
                and all(row["status"] == "projected" for row in rows)
            ):
                return rows
        except Exception as exc:  # noqa: BLE001 - smoke test reports final projection state
            last = exc
        time.sleep(0.5)
    raise RuntimeError(
        f"Memory projection did not reach generation {generation} for {message_id}: {last}"
    )


def wait_for_task(task_id: str, expected_status: str = "completed") -> dict[str, Any]:
    deadline = time.time() + 90
    last: Any = None
    while time.time() < deadline:
        try:
            _, body = json_request("GET", f"/v1/tasks/{task_id}")
            last = body
            if body.get("status") == expected_status:
                return body
            if body.get("status") in {"failed", "cancelled"} and body.get("status") != expected_status:
                raise RuntimeError(f"Task {task_id} became terminal: {body}")
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(0.5)
    raise RuntimeError(f"Task {task_id} did not reach {expected_status}: {last}")


def blocker_codes(preflight: dict[str, Any]) -> set[str]:
    return {str(item.get("code") or "") for item in preflight.get("blockers") or []}


def main() -> None:
    wait_ready()

    # A canonical ConversationMessage is the only source needed to trigger both derived stores.
    _, routed = json_request(
        "POST",
        "/v1/assistant/commands",
        expected=202,
        payload={
            "text": "Quelles sont les nouvelles du jour sur la ville de Lyon ?",
            "locale": "fr-FR",
            "output": "auto",
        },
    )
    conversation_id = routed["conversation_id"]
    _, before_messages = json_request(
        "GET", f"/v1/conversations/{conversation_id}/messages"
    )
    assert len(before_messages) == 1, before_messages
    message = before_messages[0]
    message_id = message["id"]
    canonical_snapshot = json.loads(json.dumps(before_messages, sort_keys=True))

    first = wait_for_projection(message_id, 1)
    assert {row["projector"] for row in first} == {"mem0", "graphiti"}, first
    first_task_id = expected_task_id(message_id, 1)
    assert {row["task_id"] for row in first} == {first_task_id}, first
    assert all(row["metadata"]["backend"] == "deterministic-stub" for row in first), first
    first_keys = {row["projector"]: row["projection_key"] for row in first}
    assert first_keys == {
        "mem0": f"stub:mem0:{message_id}",
        "graphiti": f"stub:graphiti:{message_id}",
    }, first_keys

    _, first_task = json_request("GET", f"/v1/tasks/{first_task_id}")
    assert first_task["status"] == "completed", first_task
    assert first_task["input"]["capability"] == "memory.project", first_task
    assert first_task["input"]["source_id"] == message_id, first_task
    assert first_task["input"]["projection_generation"] == 1, first_task

    # Rebuild does not rewrite the canonical message. It advances only the projection generation,
    # which creates a new deterministic Temporal Task while keeping external projection identity
    # stable for the same canonical source.
    _, rebuild = json_request(
        "POST",
        "/internal/v1/memory/rebuild",
        payload={"message_ids": [message_id]},
        headers=INTERNAL_HEADERS,
    )
    assert rebuild["queued"] == 1, rebuild
    assert rebuild["messages"] == [{"message_id": message_id, "generation": 2}], rebuild

    second = wait_for_projection(message_id, 2)
    second_task_id = expected_task_id(message_id, 2)
    assert second_task_id != first_task_id
    assert {row["task_id"] for row in second} == {second_task_id}, second
    second_keys = {row["projector"]: row["projection_key"] for row in second}
    assert second_keys == first_keys, (first_keys, second_keys)

    _, second_task = json_request("GET", f"/v1/tasks/{second_task_id}")
    assert second_task["status"] == "completed", second_task
    assert second_task["input"]["projection_generation"] == 2, second_task

    # A delayed generation-1 delivery cannot roll the projection back after a rebuild.
    _, stale = json_request(
        "POST",
        f"/internal/v1/memory/projections/conversation-messages/{message_id}/ensure",
        payload={"generation": 1},
        headers=INTERNAL_HEADERS,
    )
    assert stale["status"] == "superseded", stale
    assert stale["generation"] == 2, stale
    assert stale["should_run"] is False, stale

    _, preflight_before_purge = json_request("GET", "/v1/account/erasure/preflight")
    assert preflight_before_purge["inventory"]["derived_projections"]["purge_adapter_available"] is True
    assert preflight_before_purge["inventory"]["derived_projections"]["purge_current"] is False
    assert "derived_projection_purge_required" in blocker_codes(preflight_before_purge)

    # The user-facing purge runs through the same durable Task/Temporal execution substrate. In this
    # integration stack the projectors are deterministic stubs, so the proof exercises lifecycle,
    # owner binding, ledger clearing and canonical preservation without needing Mem0/Neo4j binaries.
    _, purge = json_request("POST", "/v1/account/derived-memory/purge", expected=202)
    purge_task = wait_for_task(purge["task_id"])
    assert purge_task["input"]["capability"] == "memory.purge", purge_task
    assert purge_task["input"]["policy_scope"]["canonical_conversations_preserved"] is True

    _, purged_projection = json_request(
        "GET", f"/v1/memory/projections/conversation-messages/{message_id}"
    )
    assert purged_projection["projectors"] == [], purged_projection

    _, preflight_after_purge = json_request("GET", "/v1/account/erasure/preflight")
    derived = preflight_after_purge["inventory"]["derived_projections"]
    assert derived["memory_projection_records"] == 0, derived
    assert derived["purge_current"] is True, derived
    assert derived["latest_completed_purge_cutoff_at"] is not None, derived
    assert "derived_projection_purge_required" not in blocker_codes(preflight_after_purge)

    _, after_messages = json_request(
        "GET", f"/v1/conversations/{conversation_id}/messages"
    )
    assert json.loads(json.dumps(after_messages, sort_keys=True)) == canonical_snapshot, (
        canonical_snapshot,
        after_messages,
    )

    print(
        "MEMORY PROJECTION INTEGRATION PASS: canonical ConversationMessage events drive "
        "deterministic Temporal projection Tasks, Mem0/Graphiti projections rebuild by generation, "
        "stale deliveries cannot roll state back, derived memory can be purged through a durable "
        "user action, and canonical conversation data remains unchanged."
    )


if __name__ == "__main__":
    main()
