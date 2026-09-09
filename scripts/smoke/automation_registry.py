#!/usr/bin/env python3
"""Proof for the KAIRO-owned Automation registry without crossing the external webhook boundary."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

CORE = "http://localhost:8000"


def json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(CORE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8")) if response.status != 204 else None
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
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"KAIRO Core did not become ready: {last_error}")


def main() -> None:
    wait_ready()

    _, project = json_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={
            "name": "Automation Registry Fixture",
            "status": "active",
            "summary": "Canonical automation registry smoke proof",
            "parent_id": None,
        },
    )

    _, secret = json_request(
        "POST",
        "/v1/secret-references",
        expected=201,
        payload={
            "name": "Automation webhook fixture",
            "provider_path": "secret/data/kairo/smoke/automation-webhook",
            "purpose": "Smoke-only Activepieces webhook path reference",
        },
    )

    payload = {
        "project_id": project["id"],
        "key": "fixture.automation",
        "name": "Fixture Automation",
        "description": "A disabled automation definition",
        "engine": "activepieces_webhook",
        "authority_level": 2,
        "webhook_secret_reference_id": secret["id"],
        "webhook_secret_key": "path",
        "timeout_seconds": 60,
        "metadata": {"fixture": True},
    }
    _, automation = json_request(
        "POST",
        "/v1/automations",
        expected=201,
        payload=payload,
    )
    assert automation["key"] == "fixture.automation", automation
    assert automation["engine"] == "activepieces_webhook", automation
    assert automation["enabled"] is False, automation
    assert automation["project_id"] == project["id"], automation
    assert automation["webhook_secret_reference_id"] == secret["id"], automation

    # A disabled definition cannot create execution Tasks merely because it exists.
    json_request(
        "POST",
        f"/v1/automations/{automation['id']}/runs",
        expected=409,
        payload={"input": {"fixture": "value"}, "idempotency_key": "fixture-run-disabled"},
    )

    # Metadata/lifecycle editing while disabled does not require dereferencing OpenBao.
    _, updated = json_request(
        "PATCH",
        f"/v1/automations/{automation['id']}",
        payload={
            "name": "Fixture Automation Updated",
            "description": "Still disabled and fail-closed",
            "timeout_seconds": 120,
            "authority_level": 3,
        },
    )
    assert updated["name"] == "Fixture Automation Updated", updated
    assert updated["timeout_seconds"] == 120, updated
    assert updated["authority_level"] == 3, updated
    assert updated["enabled"] is False, updated

    _, automations = json_request("GET", "/v1/automations")
    matching = [row for row in automations if row["id"] == automation["id"]]
    assert len(matching) == 1, automations
    assert matching[0]["name"] == "Fixture Automation Updated", matching[0]

    # KAIRO owns stable user-scoped keys; duplicate definitions do not silently alias a flow.
    json_request(
        "POST",
        "/v1/automations",
        expected=409,
        payload={**payload, "name": "Duplicate Automation"},
    )

    _, runs = json_request("GET", f"/v1/automation-runs?automation_id={automation['id']}")
    assert runs == [], runs

    # Enabling without a provisioned OpenBao value must fail closed. The graph CI stack does not
    # start OpenBao, so either service-unavailable or provider-side missing-secret refusal is valid.
    try:
        status, _ = json_request(
            "PATCH",
            f"/v1/automations/{automation['id']}",
            expected=503,
            payload={"enabled": True},
        )
        assert status == 503
    except AssertionError as exc:
        # If a developer happens to run this proof against a stack with OpenBao reachable but the
        # fixture secret absent, Core correctly returns 409 instead of enabling the automation.
        if "got 409" not in str(exc):
            raise

    _, after_enable_attempt = json_request("GET", "/v1/automations")
    row = next(item for item in after_enable_attempt if item["id"] == automation["id"])
    assert row["enabled"] is False, row

    print("KAIRO canonical Automation registry fail-closed proof passed")


if __name__ == "__main__":
    main()
