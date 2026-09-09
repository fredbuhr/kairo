#!/usr/bin/env python3
"""Prove SecretReference, Automation and Finance connector isolation for two Keycloak users."""

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
        raise AssertionError(f"{method} {path}: expected {expected}, got {status_code}: {parsed!r}")
    return parsed


def access_token(username: str, password: str) -> str:
    form = urllib.parse.urlencode(
        {"grant_type": "password", "client_id": CLIENT_ID, "username": username, "password": password}
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


def project(token: str, name: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/v1/projects",
        token=token,
        expected=201,
        payload={"name": name, "status": "active", "summary": None, "parent_id": None},
    )


def secret(token: str, name: str, purpose: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/v1/secret-references",
        token=token,
        expected=201,
        payload={"name": name, "purpose": purpose},
    )


def provision(token: str, reference_id: str, values: dict[str, str]) -> dict[str, Any]:
    return request_json(
        "PUT",
        f"/v1/secret-references/{reference_id}/values",
        token=token,
        payload={"values": values},
    )


def automation(token: str, project_id: str, reference_id: str, key: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/v1/automations",
        token=token,
        expected=201,
        payload={
            "project_id": project_id,
            "key": key,
            "name": key,
            "webhook_secret_reference_id": reference_id,
        },
    )


def main() -> None:
    token_a = access_token(USER_A, PASSWORD_A)
    token_b = access_token(USER_B, PASSWORD_B)
    nonce = uuid.uuid4().hex[:10]
    project_a = project(token_a, f"Secret owner A {nonce}")
    project_b = project(token_b, f"Secret owner B {nonce}")

    # Authenticated users cannot point KAIRO at an arbitrary OpenBao path.
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

    ap_a = secret(token_a, f"AP A {nonce}", "Webhook Activepieces")
    ap_b = secret(token_b, f"AP B {nonce}", "Webhook Activepieces")
    rotki_a = secret(token_a, f"Rotki A {nonce}", "Identifiants Rotki")
    rotki_b = secret(token_b, f"Rotki B {nonce}", "Identifiants Rotki")
    for reference in (ap_a, ap_b, rotki_a, rotki_b):
        assert reference["provider_path"].startswith("secret/data/kairo/users/"), reference
        assert USER_A not in reference["provider_path"] and USER_B not in reference["provider_path"], reference

    refs_a = request_json("GET", "/v1/secret-references", token=token_a)
    refs_b = request_json("GET", "/v1/secret-references", token=token_b)
    assert ap_a["id"] in ids(refs_a) and ap_b["id"] not in ids(refs_a), refs_a
    assert ap_b["id"] in ids(refs_b) and ap_a["id"] not in ids(refs_b), refs_b
    assert rotki_a["id"] in ids(refs_a) and rotki_b["id"] not in ids(refs_a), refs_a
    assert rotki_b["id"] in ids(refs_b) and rotki_a["id"] not in ids(refs_b), refs_b

    # Foreign reference IDs collapse to 404 on every public read/write metadata surface.
    request_json("GET", f"/v1/secret-references/{ap_b['id']}", token=token_a, expected=404)
    request_json("GET", f"/v1/secret-references/{ap_b['id']}/status", token=token_a, expected=404)
    request_json(
        "PATCH",
        f"/v1/secret-references/{ap_b['id']}",
        token=token_a,
        expected=404,
        payload={"name": "must not mutate"},
    )
    request_json(
        "PUT",
        f"/v1/secret-references/{ap_b['id']}/values",
        token=token_a,
        expected=404,
        payload={"values": {"path": "must-not-write"}},
    )
    request_json(
        "DELETE",
        f"/v1/secret-references/{ap_b['id']}/values",
        token=token_a,
        expected=404,
    )

    status_a = provision(token_a, ap_a["id"], {"path": f"ownership-a-{nonce}"})
    status_b = provision(token_b, ap_b["id"], {"path": f"ownership-b-{nonce}"})
    rotki_status_a = provision(
        token_a,
        rotki_a["id"],
        {"username": f"user-a-{nonce}", "password": f"password-a-{nonce}"},
    )
    rotki_status_b = provision(
        token_b,
        rotki_b["id"],
        {"username": f"user-b-{nonce}", "password": f"password-b-{nonce}"},
    )
    assert status_a["keys"] == ["path"] and "ownership-a" not in json.dumps(status_a), status_a
    assert status_b["keys"] == ["path"] and "ownership-b" not in json.dumps(status_b), status_b
    assert rotki_status_a["keys"] == ["password", "username"], rotki_status_a
    assert rotki_status_b["keys"] == ["password", "username"], rotki_status_b
    read_status_a = request_json("GET", f"/v1/secret-references/{rotki_a['id']}/status", token=token_a)
    assert read_status_a["exists"] is True and read_status_a["keys"] == ["password", "username"], read_status_a
    assert "password-a" not in json.dumps(read_status_a), read_status_a

    # Provider values and the canonical reference have intentionally separate retention semantics.
    # A populated reference cannot be removed as metadata-only, another user cannot revoke it, and
    # explicit value destruction removes all KV-v2 versions before the now-empty handle can be deleted.
    retention = secret(token_a, f"Retention A {nonce}", "Retention proof")
    provision(token_a, retention["id"], {"token": f"retention-{nonce}"})
    request_json(
        "DELETE",
        f"/v1/secret-references/{retention['id']}",
        token=token_a,
        expected=409,
    )
    request_json(
        "DELETE",
        f"/v1/secret-references/{retention['id']}/values",
        token=token_b,
        expected=404,
    )
    request_json(
        "DELETE",
        f"/v1/secret-references/{retention['id']}/values",
        token=token_a,
        expected=204,
    )
    emptied = request_json(
        "GET",
        f"/v1/secret-references/{retention['id']}/status",
        token=token_a,
    )
    assert emptied["exists"] is False and emptied["keys"] == [], emptied
    request_json(
        "DELETE",
        f"/v1/secret-references/{retention['id']}",
        token=token_a,
        expected=204,
    )
    request_json("GET", f"/v1/secret-references/{retention['id']}", token=token_a, expected=404)

    # Foreign Projects and SecretReferences are refused before database constraint fallback.
    request_json(
        "POST",
        "/v1/automations",
        token=token_a,
        expected=404,
        payload={
            "project_id": project_b["id"],
            "key": f"cross-project-{nonce}",
            "name": "Cross project",
            "webhook_secret_reference_id": ap_a["id"],
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
            "webhook_secret_reference_id": ap_b["id"],
        },
    )

    automation_a = automation(token_a, project_a["id"], ap_a["id"], f"owned-a-{nonce}")
    automation_b = automation(token_b, project_b["id"], ap_b["id"], f"owned-b-{nonce}")
    assert automation_a["enabled"] is False and automation_b["enabled"] is False
    request_json("PATCH", f"/v1/automations/{automation_a['id']}", token=token_a, payload={"enabled": True})
    request_json("PATCH", f"/v1/automations/{automation_b['id']}", token=token_b, payload={"enabled": True})
    request_json(
        "PATCH",
        f"/v1/automations/{automation_b['id']}",
        token=token_a,
        expected=404,
        payload={"name": "must not mutate"},
    )
    request_json(
        "DELETE",
        f"/v1/secret-references/{ap_a['id']}",
        token=token_a,
        expected=409,
    )

    # Idempotency is scoped to one AutomationDefinition, not globally across tenants.
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

    # Finance connector configuration obeys the same owner boundary without contacting Rotki.
    for bad_project, bad_secret, suffix in (
        (project_a["id"], rotki_b["id"], "secret"),
        (project_b["id"], rotki_a["id"], "project"),
    ):
        request_json(
            "POST",
            "/v1/finance/connectors",
            token=token_a,
            expected=404,
            payload={
                "project_id": bad_project,
                "key": f"cross-finance-{suffix}-{nonce}",
                "display_name": f"Cross finance {suffix}",
                "secret_reference_id": bad_secret,
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
    request_json(
        "PATCH",
        f"/v1/finance/connectors/{finance_b['id']}",
        token=token_a,
        expected=404,
        payload={"display_name": "must not mutate"},
    )
    connectors_a = request_json("GET", "/v1/finance/connectors", token=token_a)
    connectors_b = request_json("GET", "/v1/finance/connectors", token=token_b)
    assert finance_a["id"] in ids(connectors_a) and finance_b["id"] not in ids(connectors_a), connectors_a
    assert finance_b["id"] in ids(connectors_b) and finance_a["id"] not in ids(connectors_b), connectors_b

    print("KAIRO SecretReference/Automation/Finance two-user ownership + retention proof passed")


if __name__ == "__main__":
    main()
