#!/usr/bin/env python3
"""Prove account inventory/export/preflight stay subject-scoped with two real Keycloak users."""

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
    data = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        }
    ).encode()
    request = urllib.request.Request(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data=data,
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
            status = response.status
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode()
    body = json.loads(raw) if raw else None
    if status != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {body!r}")
    return body


def blocker_count(preflight: dict[str, Any], code: str) -> int:
    for blocker in preflight.get("blockers", []):
        if blocker.get("code") == code:
            return int(blocker.get("count") or 0)
    return 0


def main() -> None:
    a = token(USER_A, PASSWORD_A)
    b = token(USER_B, PASSWORD_B)
    nonce = uuid.uuid4().hex[:10]

    before_a = request_json("GET", "/v1/account/data-inventory", a)
    before_b = request_json("GET", "/v1/account/data-inventory", b)
    preflight_a = request_json("GET", "/v1/account/erasure/preflight", a)
    preflight_b = request_json("GET", "/v1/account/erasure/preflight", b)

    project_a = request_json(
        "POST",
        "/v1/projects",
        a,
        expected=201,
        payload={
            "name": f"Lifecycle A {nonce}",
            "status": "active",
            "summary": "account lifecycle isolation proof",
            "parent_id": None,
        },
    )
    request_json(
        "POST",
        "/v1/tasks",
        a,
        expected=201,
        payload={
            "project_id": project_a["id"],
            "title": f"Lifecycle active task {nonce}",
            "input": {},
        },
    )

    after_a = request_json("GET", "/v1/account/data-inventory", a)
    after_b = request_json("GET", "/v1/account/data-inventory", b)
    after_preflight_a = request_json("GET", "/v1/account/erasure/preflight", a)
    after_preflight_b = request_json("GET", "/v1/account/erasure/preflight", b)

    assert after_a["canonical_counts"]["projects"] == before_a["canonical_counts"]["projects"] + 1
    assert after_a["canonical_counts"]["tasks"] == before_a["canonical_counts"]["tasks"] + 1
    assert after_b["canonical_counts"]["projects"] == before_b["canonical_counts"]["projects"]
    assert after_b["canonical_counts"]["tasks"] == before_b["canonical_counts"]["tasks"]

    # Project + Task creation each emit one owner-tagged Audit row and one owner-tagged Outbox row.
    # The exact published/unpublished split may change while the relay is running; total ownership
    # must be stable and user B must not absorb A's evidence.
    assert after_a["evidence"]["data_subject_addressable"] is True
    assert after_a["evidence"]["retention_action_available"] is True
    assert after_a["evidence"]["subject_owned_audit_records"] >= before_a["evidence"]["subject_owned_audit_records"] + 2
    assert after_a["evidence"]["subject_owned_outbox_events"] >= before_a["evidence"]["subject_owned_outbox_events"] + 2
    assert after_b["evidence"]["subject_owned_audit_records"] == before_b["evidence"]["subject_owned_audit_records"]
    assert after_b["evidence"]["subject_owned_outbox_events"] == before_b["evidence"]["subject_owned_outbox_events"]

    assert blocker_count(after_preflight_a, "active_tasks") == blocker_count(preflight_a, "active_tasks") + 1
    assert blocker_count(after_preflight_b, "active_tasks") == blocker_count(preflight_b, "active_tasks")
    evidence_blocker = next(
        row for row in after_preflight_a["blockers"] if row["code"] == "audit_outbox_retention_required"
    )
    assert evidence_blocker["resolvable_by_user"] is True
    assert int(evidence_blocker["count"] or 0) >= 4
    assert after_preflight_a["destructive_endpoint_available"] is False
    assert after_preflight_b["destructive_endpoint_available"] is False
    assert after_preflight_a["complete_erasure_ready"] is False

    manifest_a = request_json("GET", "/v1/account/export/manifest", a)
    manifest_b = request_json("GET", "/v1/account/export/manifest", b)
    assert manifest_a["status"] == "manifest_only" and manifest_a["bundle_export_available"] is False
    assert manifest_b["status"] == "manifest_only" and manifest_b["bundle_export_available"] is False
    assert manifest_a["inventory"]["canonical_counts"] == after_a["canonical_counts"]
    assert manifest_b["inventory"]["canonical_counts"] == after_b["canonical_counts"]
    assert manifest_a["inventory"]["evidence"] == after_a["evidence"]
    assert manifest_b["inventory"]["evidence"] == after_b["evidence"]
    assert any("secret values" in item for item in manifest_a["excludes"])

    # The public lifecycle models never expose a Keycloak subject or OpenBao provider path.
    serialized = json.dumps({"inventory": after_a, "manifest": manifest_a, "preflight": after_preflight_a})
    assert USER_A not in serialized
    assert "provider_path" not in serialized

    print("KAIRO account lifecycle + evidence two-user isolation proof passed")


if __name__ == "__main__":
    main()
