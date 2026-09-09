#!/usr/bin/env python3
"""Full-stack proof for KAIRO's read-only Rotki Finance connector.

Crosses Core -> Temporal -> Worker -> Core -> OpenBao -> controlled Rotki API -> canonical Finance
snapshot. It proves credentials stay behind OpenBao, connector creation is fail-closed, synchronization
is durable, and replayed source/account/position identity is stable while observed values can change.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

CORE = "http://localhost:8000"
OPENBAO = "http://localhost:8200"
ROTKI = "http://localhost:8090"
OPENBAO_TOKEN = os.environ.get("OPENBAO_DEV_TOKEN", "CHANGE_ME_OPENBAO")
SECRET_API_PATH = "/v1/secret/data/kairo/smoke/finance-rotki"
SECRET_REFERENCE_PATH = "secret/data/kairo/smoke/finance-rotki"
USERNAME = "kairo-smoke"
PASSWORD = "correct-horse-battery-staple"


def request_json(
    base: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = dict(headers or {})
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    body = json.loads(raw) if raw else None
    if status != expected:
        raise AssertionError(f"{method} {base}{path}: expected {expected}, got {status}: {body}")
    return status, body


def core(method: str, path: str, *, payload: dict[str, Any] | None = None, expected: int = 200) -> tuple[int, Any]:
    return request_json(CORE, method, path, payload=payload, expected=expected)


def wait_for(description: str, reader: Callable[[], Any], predicate: Callable[[Any], bool], timeout: float = 120.0) -> Any:
    deadline = time.time() + timeout
    last: Any = None
    while time.time() < deadline:
        try:
            last = reader()
            if predicate(last):
                return last
        except (OSError, urllib.error.URLError, AssertionError, json.JSONDecodeError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {description}; last={last!r}")


def wait_ready() -> None:
    wait_for(
        "KAIRO Core readiness",
        lambda: core("GET", "/health/ready")[1],
        lambda body: isinstance(body, dict) and body.get("status") == "ready",
    )
    wait_for(
        "OpenBao",
        lambda: request_json(
            OPENBAO,
            "GET",
            "/v1/sys/health",
            headers={"X-Vault-Token": OPENBAO_TOKEN},
        )[1],
        lambda body: isinstance(body, dict),
    )
    wait_for(
        "controlled Rotki fixture",
        lambda: request_json(ROTKI, "GET", "/health")[1],
        lambda body: isinstance(body, dict) and body.get("status") == "ok",
    )


def write_credentials(password: str = PASSWORD) -> None:
    request_json(
        OPENBAO,
        "POST",
        SECRET_API_PATH,
        payload={"data": {"username": USERNAME, "password": password}},
        expected=200,
        headers={"X-Vault-Token": OPENBAO_TOKEN},
    )


def wait_task(task_id: str, expected_status: str) -> dict[str, Any]:
    return wait_for(
        f"Finance Task {task_id} -> {expected_status}",
        lambda: core("GET", f"/v1/tasks/{task_id}")[1],
        lambda task: isinstance(task, dict) and task.get("status") == expected_status,
    )


def connector(connector_id: str) -> dict[str, Any]:
    _, rows = core("GET", "/v1/finance/connectors")
    return next(row for row in rows if row["id"] == connector_id)


def portfolio() -> dict[str, Any]:
    return core("GET", "/v1/finance/portfolio")[1]


def main() -> None:
    wait_ready()
    write_credentials()

    _, project = core(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "Rotki Connector Fixture", "status": "active", "summary": "Controlled Rotki integration proof"},
    )
    _, secret = core(
        "POST",
        "/v1/secret-references",
        expected=201,
        payload={
            "name": "Rotki smoke credentials",
            "provider_path": SECRET_REFERENCE_PATH,
            "purpose": "Controlled Finance connector integration proof",
        },
    )
    _, created = core(
        "POST",
        "/v1/finance/connectors",
        expected=201,
        payload={
            "project_id": project["id"],
            "key": "fixture.rotki-main",
            "provider": "rotki",
            "display_name": "Rotki Smoke Portfolio",
            "secret_reference_id": secret["id"],
            "username_secret_key": "username",
            "password_secret_key": "password",
            "source_key": "rotki.fixture-main",
            "refresh_remote": True,
            "metadata": {"fixture": "rotki-full-stack"},
        },
    )
    assert created["enabled"] is False, created
    assert "password" not in json.dumps(created["metadata_json"]).lower(), created

    core("POST", f"/v1/finance/connectors/{created['id']}/sync", expected=409)

    _, enabled = core(
        "PATCH",
        f"/v1/finance/connectors/{created['id']}",
        payload={"enabled": True},
    )
    assert enabled["enabled"] is True, enabled

    _, first_sync = core("POST", f"/v1/finance/connectors/{created['id']}/sync", expected=202)
    first_task = wait_task(first_sync["task_id"], "completed")
    assert first_task["owner_ref"] == f"kairo.finance.connector:{created['id']}", first_task

    first_connector = wait_for(
        "Rotki connector successful sync timestamp",
        lambda: connector(created["id"]),
        lambda row: bool(row.get("last_sync_at")) and not row.get("last_error"),
    )
    assert first_connector["enabled"] is True, first_connector

    first = portfolio()
    source = next(item for item in first["sources"] if item["key"] == "rotki.fixture-main")
    account = next(item for item in first["accounts"] if item["source_id"] == source["id"])
    position = next(item for item in first["positions"] if item["source_id"] == source["id"] and item["asset_key"] == "ETH")
    assert source["provider"] == "rotki", source
    assert source["external_account_ref"] == created["id"], source
    assert account["public_address"] == "0x1111111111111111111111111111111111111111", account
    assert str(position["quantity"]) in {"2", "2.000000000000000000"}, position
    assert str(position["value_usd"]) in {"5000", "5000.000000000000000000"}, position

    serialized = json.dumps(first).lower()
    assert USERNAME.lower() not in serialized, "Rotki username leaked into Finance read model"
    assert PASSWORD.lower() not in serialized, "Rotki password leaked into Finance read model"

    first_ids = (source["id"], account["id"], position["id"])
    _, fixture_state = request_json(ROTKI, "GET", "/__state")
    assert fixture_state["refresh_count"] == 1, fixture_state

    # Change the observed downstream state without changing KAIRO connector/source identity.
    request_json(ROTKI, "POST", "/__generation", payload={"generation": 2})
    _, second_sync = core("POST", f"/v1/finance/connectors/{created['id']}/sync", expected=202)
    assert second_sync["task_id"] != first_sync["task_id"], second_sync
    wait_task(second_sync["task_id"], "completed")

    second = wait_for(
        "updated sourced Rotki position",
        portfolio,
        lambda body: any(
            item.get("source_id") == first_ids[0]
            and item.get("asset_key") == "ETH"
            and str(item.get("quantity")).startswith("3.25")
            for item in body.get("positions", [])
        ),
    )
    source2 = next(item for item in second["sources"] if item["key"] == "rotki.fixture-main")
    account2 = next(item for item in second["accounts"] if item["source_id"] == source2["id"])
    position2 = next(item for item in second["positions"] if item["source_id"] == source2["id"] and item["asset_key"] == "ETH")
    assert (source2["id"], account2["id"], position2["id"]) == first_ids, (first_ids, source2, account2, position2)
    assert str(position2["value_usd"]).startswith("8125"), position2

    _, fixture_state2 = request_json(ROTKI, "GET", "/__state")
    assert fixture_state2["refresh_count"] == 2, fixture_state2

    # Credential rotation is resolved from OpenBao at execution time. A bad password must fail the
    # new durable Task without erasing the last good sourced portfolio snapshot.
    write_credentials("wrong-password")
    _, failed_sync = core("POST", f"/v1/finance/connectors/{created['id']}/sync", expected=202)
    wait_task(failed_sync["task_id"], "failed")
    failed_connector = wait_for(
        "connector error after bad credential",
        lambda: connector(created["id"]),
        lambda row: bool(row.get("last_error")),
    )
    assert failed_connector["last_sync_at"], failed_connector
    after_failure = portfolio()
    position_after_failure = next(item for item in after_failure["positions"] if item["id"] == first_ids[2])
    assert str(position_after_failure["quantity"]).startswith("3.25"), position_after_failure

    print("KAIRO Finance Core -> Temporal -> Worker -> OpenBao -> Rotki -> sourced portfolio proof passed")


if __name__ == "__main__":
    main()
