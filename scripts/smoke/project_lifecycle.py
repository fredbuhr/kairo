#!/usr/bin/env python3
"""Proof for canonical Project mutation, hierarchy cycles and graph synchronization."""

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

    _, parent = json_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "Lifecycle Parent", "status": "active", "summary": "Parent fixture"},
    )
    _, child = json_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={"name": "Lifecycle Child", "status": "active", "summary": "Child fixture"},
    )

    _, updated = json_request(
        "PATCH",
        f"/v1/projects/{child['id']}",
        payload={
            "name": "Lifecycle Child Updated",
            "summary": "Canonical mutation",
            "status": "paused",
            "parent_id": parent["id"],
        },
    )
    assert updated["name"] == "Lifecycle Child Updated", updated
    assert updated["status"] == "paused", updated
    assert updated["parent_id"] == parent["id"], updated

    # Making the parent a child of its own descendant must fail closed.
    json_request(
        "PATCH",
        f"/v1/projects/{parent['id']}",
        expected=409,
        payload={"parent_id": child["id"]},
    )

    _, home = json_request("GET", "/v1/graph/home?max_nodes=160")
    keys = {(node["entity_type"], node["id"]): node for node in home["nodes"]}
    assert ("project", child["id"]) in keys, home
    hierarchy = next(
        edge
        for edge in home["edges"]
        if edge["source"]["entity_type"] == "project"
        and edge["source"]["entity_id"] == child["id"]
        and edge["target"]["entity_type"] == "project"
        and edge["target"]["entity_id"] == parent["id"]
        and edge["relation"] == "part_of"
    )
    assert hierarchy["provenance"] == "canonical_fk", hierarchy

    _, archived = json_request(
        "PATCH",
        f"/v1/projects/{child['id']}",
        payload={"status": "archived"},
    )
    assert archived["status"] == "archived", archived

    _, after = json_request("GET", "/v1/graph/home?max_nodes=160")
    assert not any(node["entity_type"] == "project" and node["id"] == child["id"] for node in after["nodes"]), after

    print("KAIRO canonical Project lifecycle + hierarchy proof passed")


if __name__ == "__main__":
    main()
