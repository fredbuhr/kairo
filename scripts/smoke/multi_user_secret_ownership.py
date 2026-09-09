#!/usr/bin/env python3
"""Prove SecretReference, Automation and Finance connector tenant isolation.

The proof uses two real Keycloak identities against one Core/PostgreSQL/OpenBao instance. Secret
values are written only through the authenticated KAIRO API and the responses are checked to ensure
that values never come back. It also proves that foreign Projects/SecretReferences cannot be attached
to user-owned Automations or Finance connectors and that automation idempotency is definition-scoped.
"""

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


def request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(CORE + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status_code = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw = exc.read().decode("utf-8")
    parsed = json.loads(raw) if raw else None
    if status_code != expected:
        raise AssertionError(
            f"{method} {path}: expected {expected}, got {status_code}: {parsed!r}"
        )
    return parsed


def access_token(username: str, password: str) -> str:
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data=form,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = str(payload.get("access_token") or "")
    if not token:
        raise AssertionError(f"Keycloak did not return a token for {username}")
    return token


def ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("id") or "") for row in rows}


def main() -> None:
    token_a = access_token(USER_A, PASSWORD_A)
    token_b = access_token(USER_B, PASSWORD_B)
    nonce = uuid.uuid4().hex[:10]

    project_a = request_json(
        "POST",
        "/v1/projects",
        token=token_a,
        expected=201,
        payload={"name": f"Secret owner A {nonce}", "status": "active", "summary": None, "parent_id": None},
    )
    project_b = request_json(
        "POST",
        "/v1/projects",
        token=token_b,
        expected=201,
        payload={"name": f"Secret owner B {nonce}", "status": "active", "summary": None, "parent_id": None},
    )

    # Authenticated clients do not select arbitrary Vault/OpenBao paths. Core generates a private
    # subject namespace so an otherwise valid user cannot point a reference at deployment secrets.
    request_json(
        "POST",
        "/v1/secret-references",
        token=token_a,
        expected=400,
        payload={
            "name": "Must not choose provider path",
            "provider_path": "secret/data/kairo/foreign",
            "purpose": "negative fixture",
        },
    )

    activepieces_a = request_json(
        "POST",
        "/v1/secret-references",
        token=token_a,
        expected=201,
        payload={"name": f"AP A {nonce}", "purpose": "Webhook Activepieces"},
    )
    activepieces_b = request_json(
        "POST",
        "/v1/secret-references",
        token=token_b,
        expected=201,
        payload={"name": f"AP B {nonce}", "purpose": "Webhook Activepieces"},
    )
    rotki_a = request_json(
        "POST",
        "/v1/secret-references",
        token=token_a,
        expected=201,
        payload={"name": f"Rotki A {nonce}", "purpose": "Identifiants Rotki"},
    )
    rotki_b = request_json(
        "POST",
        "/v1/secret-references",
        token=token_b,
        expected=201,
        payload={"name": f"Rotki B {nonce}", "purpose": "Identifiants Rotki"},
    )

    for reference in (activepieces_a, activepieces_b, rotki_a, rotki_b):
        assert reference["provider_path"].startswith("secret/data/kairo/users/"), reference
        assert USER_A not in reference["provider_path"] and USER_B not in reference["provider_path"], reference

    refs_a = request_json("GET", "/v1/secret-references", token=token_a)
    refs_b = request_json("GET", "/v1/secret-references", token=token_b)
    assert activepieces_a["id"] in ids(refs_a) and activepieces_b["id"] not in ids(refs_a), refs_a
    assert activepieces_b["id"] in ids(refs_b) and activepieces_a["id"] not in ids(refs_b), refs_b
    assert rotki_a["id"] in ids(refs_a) and rotki_b["id"] not in ids(refs_a), refs_a
    assert rotki_b["id"] in ids(refs_b) and rotki_a["id"] not in ids(refs_b), refs_b

    # Foreign UUIDs collapse to 404 for every public secret surface.
    request_json("GET", f"/v1/secret-references/{activepieces_b['id']}", token=token_a, expected=404)
    request_json("GET", f"/v1/secret-references/{activepieces_b['id']}/status", token=token_a, expected=404)
    request_json(
        "PATCH",
        f"/v1/secret-references/{activepieces_b['id']}",
        token=token_a,
        expected=404,
        payload={"name": "must not mutate"},
    )
    request_json(
        "PUT",
        f"/v1/secret-references/{activepieces_b['id']}/values",
        token=token_a,
        expected=404,
        payload={"values": {"path": "must-not-write"}},
    )

    status_a = request_json(
        "PUT",
        f"/v1/secret-references/{activepieces_a['id']}/values",
        token=token_a,
        payload={"values": {"path": f"ownership-a-{nonce}"}},
    )
    status_b = request_json(
        "PUT",
        f"/v1/secret-references/{activepieces_b['id']}/values",
        token=token_b,
        payload={"values": {"path": f"ownership-b-{nonce}"}},
    )
    rotki_status_a = request_json(
        "PUT",
        f"/v1/secret-references/{rotki_a['id']}/values",
        token=token_a,
        payload={"values": {"username": f"user-a-{nonce}", "password": f"password-a-{nonce}"}},
    )
    rotki_status_b = request_json(
        "PUT",
        f"/v1/secret-references/{rotki_b['id']}/values",
        token=token_b,
        payload={"values": {"username": f"user-b-{nonce}", "password": f"password-b-{nonce}"}},
    )
    assert status_a["keys"] == ["path"] and "ownership-a" not in json.dumps(status_a), status_a
    assert status_b["keys"] == ["path"] and "ownership-b" not in json.dumps(status_b), status_b
    assert rotki_status_a["keys"] == ["password", "username"], rotki_status_a
    assert rotki_status_b["keys"] == ["password", "username"], rotki_status_b

    # The actual status endpoint is metadata-only as well.
    read_status_a = request_json(
        "GET", f"/v1/secret-references/{rotki_a['id']}/status", token=token_a
    )
    assert read_status_a["exists"] is True and read_status_a["keys"] == ["password", "username"], read_status_a
    assert "password-a" not in json.dumps(read_status_a), read_status_a

    # Foreign Projects or SecretReferences cannot be attached to user A's Automation definitions.
    request_json(
        "POST",
        "/v1/automations",
        token=token_a,
        expected=404,
        payload={
            "project_id": project_b["id"],
            "key": f"cross-project-{nonce}",
            "name": "Cross project",
            "webhook_secret_reference_id": activepieces_a["id"],
        },
    )
    request_json(
        "POST",
        "/v1/automations",
        token=token_a,
        expected=404,
        payload={
            "project_id": project_a["id"],
            "key": f"cross-secret-{nonce}",
            "name": "Cross secret",
            "webhook_secret_reference_id": activepieces_b["id"],
        },
    )

    automation_a = request_json(
        "POST",
        "/v1/automations",
        token=token_a,
        expected=201,
        payload={
            "project_id": project_a["id"],
            "key": f"owned-a-{nonce}",
            "name": "Owned automation A",
            "webhook_secret_reference_id": activepieces_a["id"],
        },
    )
    automation_b = request_json(
        "POST",
        "/v1/automations",
        token=token_b,
        expected=201,
        payload={
            "project_id": project_b["id"],
            "key": f"owned-b-{nonce}",
            "name": "Owned automation B",
            "webhook_secret_reference_id": activepieces_b["id"],
        },
    )
    assert automation_a["enabled"] is False and automation_b["enabled"] is False
    request_json("PATCH", f"/v1/automations/{automation_a['id']}", token=token_a, payload={"enabled": True})
    request_json("PATCH", f"/v1/automations/{automation_b['id']}", token=token_b, payload={"enabled": True})

    # Same human-chosen idempotency key is valid in two independent automation definitions. No
    # global uniqueness oracle should couple two tenants. No Worker is required to prove creation;
    # Temporal can accept the durable workflow and leave it queued in this isolation stack.
    shared_key = f"shared-human-key-{nonce}"
    run_a = request_json(
        "POST",
        f"/v1/automations/{automation_a['id']}/runs",
        token=token_a,
        expected=202,
        payload={"input": {"tenant": "a"}, "idempotency_key": shared_key},
    )
    run_b = request_json(
        "POST",
        f"/v1/automations/{automation_b['id']}/runs",
        token=token_b,
        expected=202,
        payload={"input": {"tenant": "b"}, "idempotency_key": shared_key},
    )
    assert run_a["invocation"]["id"] != run_b["invocation"]["id"], (run_a, run_b)

    # Finance connectors obey the same Project/Secret owner rules before any Rotki request exists.
    request_json(
        "POST",
        "/v1/finance/connectors",
        token=token_a,
        expected=404,
        payload={
            "project_id": project_a["id"],
            "key": f"cross-finance-secret-{nonce}",
            "display_name": "Cross finance secret",
            "secret_reference_id": rotki_b["id"],
        },
    )
    request_json(
        "POST",
        "/v1/finance/connectors",
        token=token_a,
        expected=404,
        payload={
            "project_id": project_b["id"],
            "key": f"cross-finance-project-{nonce}",
            "display_name": "Cross finance project",
            "secret_reference_id": rotki_a["id"],
        },
    )
    finance_a = request_json(
        "POST",
        "/v1/finance/connectors",
        token=token_a,
        expected=201,
        payload={
            "project_id": project_a["id"],
            "key": f"finance-a-{nonce}",
            "display_name": "Finance A",
            "secret_reference_id": rotki_a["id"],
        },
    )
    finance_b = request_json(
        "POST",
        "/v1/finance/connectors",
        token=token_b,
        expected=201,
        payload={
            "project_id": project_b["id"],
            "key": f"finance-b-{nonce}",
            "display_name": "Finance B",
            "secret_reference_id": rotki_b["id"],
        },
    )
    assert finance_a["enabled"] is False and finance_b["enabled"] is False
    request_json("GET", f"/v1/finance/connectors/{finance_b['id']}", token=token_a, expected=404)

    print("KAIRO SecretReference/Automation/Finance two-user ownership proof passed")


if __name__ == "__main__":
    main()
