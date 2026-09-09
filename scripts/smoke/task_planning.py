#!/usr/bin/env python3
"""End-to-end proof for explicit KAIRO Task planning and Today projection."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
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
        payload={"name": "Today Smoke Project", "status": "active", "summary": "Planning proof"},
    )
    _, task = json_request(
        "POST",
        "/v1/tasks",
        expected=201,
        payload={
            "project_id": project["id"],
            "title": "Explicit Today planning",
            "description": "Must appear only because canonical planning fields say so.",
            "authority_ceiling": 1,
            "input": {},
        },
    )

    _, planning = json_request("GET", "/v1/planning/tasks?include_closed=true")
    created = next(item for item in planning if item["id"] == task["id"])
    assert created["priority"] == 2, created
    assert created["due_at"] is None, created

    now = datetime.now(UTC)
    # Shift the projected local clock close to noon so now+30m cannot straddle the local day boundary.
    offset_minutes = 12 * 60 - (now.hour * 60 + now.minute)
    due = now + timedelta(minutes=30)
    start = now - timedelta(minutes=10)
    end = now + timedelta(minutes=50)

    _, updated = json_request(
        "PATCH",
        f"/v1/tasks/{task['id']}/planning",
        payload={
            "priority": 4,
            "planned_start_at": start.isoformat(),
            "planned_end_at": end.isoformat(),
            "due_at": due.isoformat(),
            "status": "in_progress",
        },
    )
    assert updated["priority"] == 4, updated
    assert updated["status"] == "in_progress", updated
    assert updated["started_at"] is not None, updated

    _, today = json_request("GET", f"/v1/today?timezone_offset_minutes={offset_minutes}")
    due_ids = {item["id"] for item in today["due_today"]}
    assert task["id"] in due_ids, today
    assert all(item["id"] != task["id"] for item in today["important"]), today

    # Invalid canonical intervals fail instead of being silently repaired by the UI.
    json_request(
        "PATCH",
        f"/v1/tasks/{task['id']}/planning",
        expected=422,
        payload={
            "planned_start_at": end.isoformat(),
            "planned_end_at": start.isoformat(),
        },
    )

    _, completed = json_request(
        "PATCH",
        f"/v1/tasks/{task['id']}/planning",
        payload={"status": "completed"},
    )
    assert completed["completed_at"] is not None, completed

    _, after = json_request("GET", f"/v1/today?timezone_offset_minutes={offset_minutes}")
    projected_ids = {
        item["id"]
        for group in ("overdue", "due_today", "planned_today", "important")
        for item in after[group]
    }
    assert task["id"] not in projected_ids, after

    print("KAIRO explicit Task planning + Today projection smoke proof passed")


if __name__ == "__main__":
    main()
