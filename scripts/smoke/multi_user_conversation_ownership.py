#!/usr/bin/env python3
"""Prove owner isolation across Assistant, News, Memory and task-run public surfaces."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

CORE = os.getenv("KAIRO_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "kairo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "kairo-web")
USER_A = os.getenv("KEYCLOAK_DEV_USERNAME", "kairo-dev")
PASSWORD_A = os.getenv("KEYCLOAK_DEV_PASSWORD", "kairo-dev")
USER_B = os.getenv("KEYCLOAK_ALT_USERNAME", "kairo-alt")
PASSWORD_B = os.getenv("KEYCLOAK_ALT_PASSWORD", "kairo-alt")


def token(username: str, password: str) -> str:
    body = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        }
    ).encode()
    request = urllib.request.Request(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    value = str(payload.get("access_token") or "")
    if not value:
        raise AssertionError(f"No access token for {username}")
    return value


def request_json(
    method: str,
    path: str,
    bearer: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept": "application/json", "Authorization": f"Bearer {bearer}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(CORE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            code = response.status
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read().decode()
    body = json.loads(raw) if raw else None
    if code != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {code}: {body!r}")
    return body


def create_project(bearer: str, name: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/v1/projects",
        bearer,
        payload={"name": name, "status": "active", "summary": "ownership fixture", "parent_id": None},
        expected=201,
    )


def create_task(bearer: str, project_id: str, title: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/v1/tasks",
        bearer,
        payload={"project_id": project_id, "title": title, "input": {}},
        expected=201,
    )


def main() -> None:
    a = token(USER_A, PASSWORD_A)
    b = token(USER_B, PASSWORD_B)
    nonce = uuid.uuid4().hex[:10]

    project_a = create_project(a, f"Assistant ownership A {nonce}")
    project_b = create_project(b, f"Assistant ownership B {nonce}")
    task_b = create_task(b, project_b["id"], f"Foreign run guard {nonce}")

    # Defense in depth: a generic task subroute cannot accidentally start another user's workflow.
    request_json("POST", f"/v1/tasks/{task_b['id']}/run", a, payload={}, expected=404)

    command_a = request_json(
        "POST",
        "/v1/assistant/commands",
        a,
        payload={"text": f"actualités générales test {nonce}", "locale": "fr-FR", "output": "text"},
        expected=202,
    )
    command_b = request_json(
        "POST",
        "/v1/assistant/commands",
        b,
        payload={"text": f"actualités générales test B {nonce}", "locale": "fr-FR", "output": "text"},
        expected=202,
    )

    conversation_a = command_a["conversation_id"]
    conversation_b = command_b["conversation_id"]
    command_id_a = command_a["command_id"]
    command_id_b = command_b["command_id"]
    news_task_a = command_a["task_id"]
    news_task_b = command_b["task_id"]

    request_json("GET", f"/v1/conversations/{conversation_a}", a)
    request_json("GET", f"/v1/conversations/{conversation_b}", b)
    request_json("GET", f"/v1/conversations/{conversation_a}", b, expected=404)
    request_json("GET", f"/v1/conversations/{conversation_b}", a, expected=404)
    request_json("GET", f"/v1/commands/{command_id_a}", b, expected=404)
    request_json("GET", f"/v1/commands/{command_id_b}", a, expected=404)

    messages_a = request_json("GET", f"/v1/conversations/{conversation_a}/messages", a)
    assert messages_a, messages_a
    message_a = messages_a[0]["id"]
    request_json("GET", f"/v1/conversations/{conversation_a}/messages", b, expected=404)

    # A foreign conversation cannot be used as a continuation target to inject a message/command.
    request_json(
        "POST",
        "/v1/assistant/commands",
        b,
        payload={
            "text": "actualités continuation interdite",
            "locale": "fr-FR",
            "output": "text",
            "conversation_id": conversation_a,
        },
        expected=404,
    )

    # News result/audio endpoints derive ownership from their per-user Task -> Project root.
    request_json("GET", f"/v1/news/briefs/{news_task_a}", a)
    request_json("GET", f"/v1/news/briefs/{news_task_b}", b)
    request_json("GET", f"/v1/news/briefs/{news_task_a}", b, expected=404)
    request_json("GET", f"/v1/news/briefs/{news_task_b}", a, expected=404)

    # Public memory projection inspection is scoped by Conversation.subject_ref.
    own_memory = request_json(
        "GET", f"/v1/memory/projections/conversation-messages/{message_a}", a
    )
    assert own_memory["message_id"] == message_a, own_memory
    request_json(
        "GET",
        f"/v1/memory/projections/conversation-messages/{message_a}",
        b,
        expected=404,
    )

    # Research rejects a foreign project before it can create a Task or Temporal execution.
    request_json(
        "POST",
        "/v1/research/runs",
        a,
        payload={
            "project_id": project_b["id"],
            "query": "cross tenant research must fail",
            "max_tool_calls": 1,
            "allowed_tool_keys": [],
            "model_alias": "local-fast",
            "estimated_model_cost_usd": "0",
        },
        expected=404,
    )

    projects_a = request_json("GET", "/v1/projects", a)
    projects_b = request_json("GET", "/v1/projects", b)
    ids_a = {row["id"] for row in projects_a}
    ids_b = {row["id"] for row in projects_b}
    assert project_a["id"] in ids_a and project_b["id"] not in ids_a
    assert project_b["id"] in ids_b and project_a["id"] not in ids_b
    # Each command creates/reuses an owner-scoped News workspace; user-visible project sets must not overlap.
    assert not ({row["id"] for row in projects_a if row["name"] == "KAIRO News"} & {row["id"] for row in projects_b if row["name"] == "KAIRO News"})

    print("KAIRO Assistant/News/Memory two-user ownership proof passed")


if __name__ == "__main__":
    main()
