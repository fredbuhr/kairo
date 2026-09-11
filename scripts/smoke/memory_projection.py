#!/usr/bin/env python3
"""End-to-end proof that KAIRO memory projections are derived and rebuildable."""

from __future__ import annotations

import json
import subprocess
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
    timeout: float = 10.0,
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
        with urllib.request.urlopen(request, timeout=timeout) as response:
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


def expected_task_id(message_id: str, generation: int) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"kairo:memory:conversation-message:{message_id}:v1:g{generation}",
        )
    )


def seed_message() -> str:
    """Commit a real source and its ORM outbox event without dispatching another capability."""

    result = subprocess.run(
        [
            "docker", "compose", "-f", "compose.yaml", "-f", "compose.test-noauth.yaml",
            "exec", "-T", "kairo-core", "python", "-",
        ],
        input='''
import asyncio
import json
from kairo_core.command_models import Conversation, ConversationMessage
from kairo_core.db import SessionFactory, engine

async def seed():
    try:
        async with SessionFactory() as session:
            conversation = Conversation(subject_ref="development-user", locale="fr-FR")
            session.add(conversation)
            await session.flush()
            session.add(ConversationMessage(
                conversation_id=conversation.id,
                role="user",
                content="Source canonique pour la projection mémoire.",
                metadata_json={"fixture": "memory-projection-smoke"},
            ))
            # ConversationMessage.after_insert creates the real transactional outbox event.
            await session.commit()
            print(json.dumps({"conversation_id": str(conversation.id)}))
    finally:
        await engine.dispose()

asyncio.run(seed())
''',
        text=True,
        capture_output=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(f"Memory source fixture failed: {result.stderr[-4000:]}")
    return str(json.loads(result.stdout)["conversation_id"])


def wait_for_task_completion(task_id: str, *, timeout: float = 90.0) -> dict[str, Any]:
    """Projection reports precede the separate Temporal completion activity."""

    deadline = time.monotonic() + timeout
    last: Any = None
    while (remaining := deadline - time.monotonic()) > 0:
        _, last = json_request("GET", f"/v1/tasks/{task_id}", timeout=min(10.0, remaining))
        if last["status"] == "completed":
            return last
        if last["status"] not in {"todo", "queued", "running"}:
            raise AssertionError(f"Memory Task {task_id} did not complete successfully: {last}")
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
    raise TimeoutError(f"Memory Task {task_id} did not complete within {timeout}s: {last}")


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


def main() -> None:
    wait_ready()
    _, existing_tasks = json_request("GET", "/v1/tasks")
    existing_task_ids = {task["id"] for task in existing_tasks}

    # Exercise ORM -> outbox -> JetStream -> Worker -> Temporal without unrelated News/LLM work.
    # Assistant command dispatch remains covered by command-kernel and semantic-command smokes.
    conversation_id = seed_message()
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

    first_task = wait_for_task_completion(first_task_id)
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

    second_task = wait_for_task_completion(second_task_id)
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

    _, after_messages = json_request(
        "GET", f"/v1/conversations/{conversation_id}/messages"
    )
    assert json.loads(json.dumps(after_messages, sort_keys=True)) == canonical_snapshot, (
        canonical_snapshot,
        after_messages,
    )

    _, after_tasks = json_request("GET", "/v1/tasks")
    created_tasks = [task for task in after_tasks if task["id"] not in existing_task_ids]
    assert {task["id"] for task in created_tasks} == {first_task_id, second_task_id}, created_tasks
    assert all(task["status"] == "completed" for task in created_tasks), created_tasks

    print(
        "MEMORY PROJECTION INTEGRATION PASS: canonical ConversationMessage events drive "
        "deterministic Temporal projection Tasks, Mem0/Graphiti projections rebuild by generation, "
        "stale deliveries cannot roll state back, and canonical conversation data is unchanged."
    )


if __name__ == "__main__":
    main()
