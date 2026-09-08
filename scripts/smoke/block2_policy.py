from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

CORE = os.getenv("KAIRO_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "kairo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "kairo-web")
USERNAME = os.getenv("KEYCLOAK_DEV_USERNAME", "kairo-dev")
PASSWORD = os.getenv("KEYCLOAK_DEV_PASSWORD", "kairo-dev")
INTERNAL_TOKEN = os.getenv("KAIRO_INTERNAL_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")


def request(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    expected: set[int] | None = None,
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            code = response.status
            raw = response.read()
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read()
    allowed = expected or {200}
    if code not in allowed:
        raise AssertionError(
            f"{method} {url} returned {code}, expected {sorted(allowed)}: {raw[:1000]!r}"
        )
    return code, raw


def json_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    internal: bool = False,
    payload: dict | None = None,
    expected: set[int] | None = None,
) -> tuple[int, dict]:
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if internal:
        headers["X-Kairo-Internal-Token"] = INTERNAL_TOKEN
    code, raw = request(method, f"{CORE}{path}", body=body, headers=headers, expected=expected)
    return code, json.loads(raw.decode()) if raw else {}


def wait_until(predicate, label: str, timeout: float = 120.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for {label}: {last!r}")


def access_token() -> str:
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": USERNAME,
            "password": PASSWORD,
        }
    ).encode()
    _, raw = request(
        "POST",
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        body=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        expected={200},
    )
    token = str(json.loads(raw.decode()).get("access_token") or "")
    if not token:
        raise AssertionError("Keycloak did not return an access token")
    return token


def create_project() -> str:
    _, project = json_request(
        "POST", "/v1/projects", payload={"name": "Block 2 Policy Proof"}, expected={201}
    )
    return str(project["id"])


def create_task(project_id: str, *, title: str, authority: int, budget: str, input_: dict) -> str:
    _, task = json_request(
        "POST",
        "/v1/tasks",
        payload={
            "project_id": project_id,
            "title": title,
            "authority_ceiling": authority,
            "budget_usd": budget,
            "input": input_,
        },
        expected={201},
    )
    return str(task["id"])


def task_state(task_id: str) -> dict:
    return json_request("GET", f"/v1/tasks/{task_id}")[1]


def main() -> int:
    wait_until(lambda: request("GET", f"{CORE}/health/live", expected={200})[0] == 200, "Core")
    token = wait_until(lambda: access_token(), "Keycloak token")
    project_id = create_project()

    # 1) High-authority workflow must suspend until an explicit approval is decided and signaled.
    guarded_task = create_task(
        project_id,
        title="Approval-gated durable action",
        authority=2,
        budget="1.00",
        input_={
            "capability": "foundation",
            "authority_level": 2,
            "estimated_cost_usd": "0.10",
            "policy_scope": {"capability": "foundation", "proof": "block2"},
            "approval_reason": "CI proves Temporal waits for KAIRO approval",
        },
    )
    _, run = json_request("POST", f"/v1/tasks/{guarded_task}/run", expected={200})
    execution_id = str(run["workflow_execution_id"])

    def pending_approval():
        _, data = json_request(
            "GET",
            f"/v1/approval-requests?task_id={guarded_task}&approval_status=pending",
            token=token,
        )
        return data[0] if data else None

    approval = wait_until(pending_approval, "pending approval")
    assert str(approval["workflow_execution_id"]) == execution_id
    time.sleep(2)
    assert task_state(guarded_task)["status"] == "running"

    approval_id = str(approval["id"])
    json_request(
        "POST",
        f"/v1/approval-requests/{approval_id}/decision",
        token=token,
        payload={"decision": "approved", "note": "Block 2 CI approval"},
    )
    _, resumed = json_request(
        "POST", f"/v1/approval-requests/{approval_id}/resume", token=token
    )
    assert resumed["signaled"] is True
    assert resumed["decision"] == "approved"
    wait_until(lambda: task_state(guarded_task)["status"] == "completed", "approved workflow completion")

    # 2) A hard budget is checked before activity execution and fails closed.
    budget_task = create_task(
        project_id,
        title="Budget-denied action",
        authority=1,
        budget="0.05",
        input_={
            "capability": "foundation",
            "authority_level": 1,
            "estimated_cost_usd": "0.10",
        },
    )
    json_request("POST", f"/v1/tasks/{budget_task}/run", expected={200})
    wait_until(lambda: task_state(budget_task)["status"] == "failed", "hard-budget denial")

    # 3) Low-authority policy calls receive short signed capabilities; mismatched validation fails.
    direct_task = create_task(
        project_id,
        title="Direct policy token proof",
        authority=1,
        budget="1.00",
        input_={},
    )
    _, authorized = json_request(
        "POST",
        "/internal/v1/policy/authorize",
        internal=True,
        payload={
            "task_id": direct_task,
            "action": "research.read",
            "authority_level": 1,
            "estimated_cost_usd": "0.01",
            "scope": {"mode": "read-only"},
        },
    )
    assert authorized["allowed"] is True
    assert authorized["policy_token"]
    _, valid = json_request(
        "POST",
        "/internal/v1/policy/validate",
        internal=True,
        payload={
            "policy_token": authorized["policy_token"],
            "task_id": direct_task,
            "action": "research.read",
        },
    )
    assert valid["valid"] is True
    _, invalid = json_request(
        "POST",
        "/internal/v1/policy/validate",
        internal=True,
        payload={
            "policy_token": authorized["policy_token"],
            "task_id": str(uuid.uuid4()),
            "action": "research.read",
        },
    )
    assert invalid["valid"] is False

    # 4) Model spend is canonical, visible through the task budget contract and idempotent.
    correlation_id = str(uuid.uuid4())
    idempotency_key = f"ci-model-{uuid.uuid4()}"
    usage_payload = {
        "task_id": direct_task,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "provider": "ci",
        "model_alias": "smart",
        "model_name": "deterministic-proof",
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "cost_usd": "0.25",
        "metadata": {"proof": "block2", "idempotency_key": idempotency_key},
    }
    _, budget = json_request(
        "POST",
        "/internal/v1/model-usage",
        internal=True,
        payload=usage_payload,
    )
    assert budget["spent_usd"] == "0.250000"

    # Replay the exact same accounting write, as would happen after a lost HTTP response. It must
    # return success without inserting or charging a second time.
    _, replay_budget = json_request(
        "POST",
        "/internal/v1/model-usage",
        internal=True,
        payload=usage_payload,
    )
    assert replay_budget["spent_usd"] == "0.250000"

    _, public_budget = json_request("GET", f"/v1/tasks/{direct_task}/budget", token=token)
    assert public_budget["spent_usd"] == "0.250000"
    assert public_budget["remaining_usd"] == "0.750000"

    print(
        "BLOCK 2 POLICY SMOKE PASSED: Temporal approval suspension/resume, hard budgets, signed "
        "policy capabilities and idempotent canonical model spend are proven."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
