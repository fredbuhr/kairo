#!/usr/bin/env python3
"""Full-stack proof for KAIRO Automation execution and ambiguous-outcome handling.

The proof crosses Core -> Temporal -> Worker -> OpenBao -> a controlled webhook transport that models
the Activepieces webhook contract. It deliberately verifies both a successful call and a downstream
call whose request is accepted but whose response disappears. The latter must be recorded as
ambiguous and must never be replayed automatically.
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
WEBHOOK = "http://localhost:8089"
OPENBAO_TOKEN = os.environ.get("OPENBAO_DEV_TOKEN", "CHANGE_ME_OPENBAO")
SECRET_API_PATH = "/v1/secret/data/kairo/smoke/automation-full-stack"
SECRET_REFERENCE_PATH = "secret/data/kairo/smoke/automation-full-stack"


def request_json(
    base: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = dict(headers or {})
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers=request_headers,
    )
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


def core(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
) -> tuple[int, Any]:
    return request_json(CORE, method, path, payload=payload, expected=expected)


def wait_for(description: str, reader: Callable[[], Any], predicate: Callable[[Any], bool], timeout: float = 90.0) -> Any:
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
    raise RuntimeError(f"Timed out waiting for {description}; last value={last!r}")


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
        "controlled webhook fixture",
        lambda: request_json(WEBHOOK, "GET", "/health")[1],
        lambda body: isinstance(body, dict) and body.get("status") == "ok",
    )


def write_webhook_path(path: str) -> None:
    request_json(
        OPENBAO,
        "POST",
        SECRET_API_PATH,
        payload={"data": {"path": path}},
        expected=200,
        headers={"X-Vault-Token": OPENBAO_TOKEN},
    )


def automation_run(automation_id: str, invocation_id: str) -> dict[str, Any] | None:
    _, runs = core("GET", f"/v1/automation-runs?automation_id={automation_id}&limit=50")
    for run in runs:
        if run["id"] == invocation_id:
            return run
    return None


def wait_run(automation_id: str, invocation_id: str, status: str) -> dict[str, Any]:
    return wait_for(
        f"automation invocation {invocation_id} -> {status}",
        lambda: automation_run(automation_id, invocation_id),
        lambda run: isinstance(run, dict) and run.get("status") == status,
        timeout=120,
    )


def wait_task(task_id: str, status: str) -> dict[str, Any]:
    return wait_for(
        f"Task {task_id} -> {status}",
        lambda: core("GET", f"/v1/tasks/{task_id}")[1],
        lambda task: isinstance(task, dict) and task.get("status") == status,
        timeout=120,
    )


def records() -> list[dict[str, Any]]:
    _, body = request_json(WEBHOOK, "GET", "/__records")
    return body["records"]


def main() -> None:
    wait_ready()
    write_webhook_path("success")

    _, project = core(
        "POST",
        "/v1/projects",
        expected=201,
        payload={
            "name": "Automation Full Stack Fixture",
            "status": "active",
            "summary": "Temporal Worker/OpenBao/webhook smoke proof",
            "parent_id": None,
        },
    )
    _, secret = core(
        "POST",
        "/v1/secret-references",
        expected=201,
        payload={
            "name": "Automation full-stack webhook",
            "provider_path": SECRET_REFERENCE_PATH,
            "purpose": "Controlled automation integration proof",
        },
    )
    _, automation = core(
        "POST",
        "/v1/automations",
        expected=201,
        payload={
            "project_id": project["id"],
            "key": "fixture.automation-full-stack",
            "name": "Automation Full Stack",
            "description": "Controlled Worker webhook boundary proof",
            "engine": "activepieces_webhook",
            # A1 keeps this transport proof focused on execution. Higher-authority approval behavior
            # is already proved by the shared policy/approval tests used by all capability Tasks.
            "authority_level": 1,
            "webhook_secret_reference_id": secret["id"],
            "webhook_secret_key": "path",
            "timeout_seconds": 15,
            "metadata": {"fixture": "full-stack"},
        },
    )
    assert automation["enabled"] is False, automation

    _, enabled = core(
        "PATCH",
        f"/v1/automations/{automation['id']}",
        payload={"enabled": True},
    )
    assert enabled["enabled"] is True, enabled

    success_input = {"operation": "success", "value": 42}
    _, success_created = core(
        "POST",
        f"/v1/automations/{automation['id']}/runs",
        expected=202,
        payload={"input": success_input, "idempotency_key": "automation-full-stack-success"},
    )
    success_invocation = success_created["invocation"]
    success_task_id = success_created["task_id"]
    success_run = wait_run(automation["id"], success_invocation["id"], "completed")
    success_task = wait_task(success_task_id, "completed")
    assert success_run["response_status"] == 202, success_run
    assert success_run["outcome_ambiguous"] is False, success_run
    assert success_run["result_json"]["response_size_bytes"] > 0, success_run
    assert len(success_run["result_json"]["response_sha256"]) == 64, success_run
    assert success_task["owner_ref"] == "kairo.automation-runtime", success_task

    success_records = [row for row in records() if row["path"] == "/success"]
    assert len(success_records) == 1, success_records
    assert success_records[0]["invocation_id"] == success_invocation["id"], success_records[0]
    assert success_records[0]["correlation_id"], success_records[0]
    assert success_records[0].get("json") == success_input, success_records[0]

    # Rotate only the OpenBao value. KAIRO resolves it again at execution time rather than freezing
    # the downstream path into PostgreSQL or the canonical Task snapshot.
    write_webhook_path("ambiguous")
    ambiguous_input = {"operation": "ambiguous", "value": 7}
    _, ambiguous_created = core(
        "POST",
        f"/v1/automations/{automation['id']}/runs",
        expected=202,
        payload={"input": ambiguous_input, "idempotency_key": "automation-full-stack-ambiguous"},
    )
    ambiguous_invocation = ambiguous_created["invocation"]
    ambiguous_task_id = ambiguous_created["task_id"]
    ambiguous_run = wait_run(automation["id"], ambiguous_invocation["id"], "failed")
    ambiguous_task = wait_task(ambiguous_task_id, "failed")
    assert ambiguous_run["outcome_ambiguous"] is True, ambiguous_run
    assert ambiguous_run["response_status"] is None, ambiguous_run
    assert ambiguous_run["last_error"], ambiguous_run
    assert ambiguous_task["status"] == "failed", ambiguous_task

    ambiguous_records = [row for row in records() if row["path"] == "/ambiguous"]
    assert len(ambiguous_records) == 1, ambiguous_records
    assert ambiguous_records[0]["invocation_id"] == ambiguous_invocation["id"], ambiguous_records[0]
    assert ambiguous_records[0].get("json") == ambiguous_input, ambiguous_records[0]

    # Public idempotent retry of the same terminal request returns the same canonical invocation.
    # It must not create a second Task or repeat the webhook whose first outcome is uncertain.
    _, replay = core(
        "POST",
        f"/v1/automations/{automation['id']}/runs",
        expected=202,
        payload={"input": ambiguous_input, "idempotency_key": "automation-full-stack-ambiguous"},
    )
    assert replay["invocation"]["id"] == ambiguous_invocation["id"], replay
    assert replay["task_id"] == ambiguous_task_id, replay
    time.sleep(2)
    ambiguous_records_after = [row for row in records() if row["path"] == "/ambiguous"]
    assert len(ambiguous_records_after) == 1, ambiguous_records_after

    print("KAIRO Automation Core -> Temporal -> Worker -> OpenBao -> webhook proof passed")


if __name__ == "__main__":
    main()
