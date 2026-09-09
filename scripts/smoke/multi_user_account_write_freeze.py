#!/usr/bin/env python3
"""Prove a local account write freeze blocks stale-bearer mutations for one subject only."""

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


def create_project(bearer: str, label: str, *, expected: int = 201) -> Any:
    return request_json(
        "POST",
        "/v1/projects",
        bearer,
        expected=expected,
        payload={"name": label, "status": "active", "parent_id": None},
    )


def main() -> None:
    a = token(USER_A, PASSWORD_A)
    b = token(USER_B, PASSWORD_B)
    nonce = uuid.uuid4().hex[:10]

    state_a = request_json("GET", "/v1/account/erasure/write-freeze", a)
    state_b = request_json("GET", "/v1/account/erasure/write-freeze", b)
    assert state_a["frozen"] is False, state_a
    assert state_b["frozen"] is False, state_b

    before_a = create_project(a, f"Freeze before A {nonce}")
    before_b = create_project(b, f"Freeze before B {nonce}")

    frozen = request_json(
        "POST",
        "/v1/account/erasure/write-freeze",
        a,
        expected=201,
        payload={
            "confirmation": "FREEZE_ACCOUNT_WRITES",
            "reason": "two-user stale-bearer proof",
        },
    )
    assert frozen["frozen"] is True, frozen
    assert frozen["operation_id"], frozen
    assert frozen["blocks_public_mutations"] is True
    assert frozen["keycloak_identity_changed"] is False

    replay = request_json(
        "POST",
        "/v1/account/erasure/write-freeze",
        a,
        expected=201,
        payload={"confirmation": "FREEZE_ACCOUNT_WRITES"},
    )
    assert replay["operation_id"] == frozen["operation_id"], (replay, frozen)

    # Reads remain available through the same already-issued bearer.
    projects_a = request_json("GET", "/v1/projects", a)
    assert before_a["id"] in {row["id"] for row in projects_a}

    # The same bearer can no longer mutate ordinary user-world state.
    blocked = create_project(a, f"Freeze blocked A {nonce}", expected=423)
    assert blocked["code"] == "account_write_frozen", blocked

    # Another authenticated subject remains fully independent.
    after_b = create_project(b, f"Freeze unaffected B {nonce}")
    assert after_b["id"] != before_b["id"]
    state_b_after = request_json("GET", "/v1/account/erasure/write-freeze", b)
    assert state_b_after["frozen"] is False, state_b_after

    # A can reverse this local-only freeze because no irreversible account-erasure phase exists yet.
    unfrozen = request_json(
        "POST",
        "/v1/account/erasure/write-freeze/cancel",
        a,
        payload={"confirmation": "UNFREEZE_ACCOUNT_WRITES"},
    )
    assert unfrozen["frozen"] is False, unfrozen
    after_a = create_project(a, f"Freeze after A {nonce}")
    assert after_a["id"] != before_a["id"]

    print("KAIRO two-user local account write-freeze proof passed")


if __name__ == "__main__":
    main()
