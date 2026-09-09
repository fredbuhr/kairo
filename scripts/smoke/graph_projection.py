#!/usr/bin/env python3
"""Smoke proof for KAIRO's canonical spatial graph read model."""

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
    request = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
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
        except Exception as exc:  # noqa: BLE001 - smoke test reports the final readiness failure
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"KAIRO Core did not become ready: {last_error}")


def entity_key(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def main() -> None:
    wait_ready()

    _, project = json_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={
            "name": "Spatial Graph Smoke Project",
            "status": "active",
            "summary": "Canonical project used to prove KAIRO spatial graph projection.",
        },
    )
    _, task = json_request(
        "POST",
        "/v1/tasks",
        expected=201,
        payload={
            "project_id": project["id"],
            "title": "Prove spatial graph read model",
            "status": "todo",
            "authority_ceiling": 1,
            "input": {},
        },
    )
    _, relationship = json_request(
        "POST",
        "/v1/relationships",
        expected=201,
        payload={
            "source_type": "project",
            "source_id": project["id"],
            "relation_type": "tracks",
            "target_type": "task",
            "target_id": task["id"],
            "metadata": {
                "directed": True,
                "strength": 0.81,
                "explanation": "Smoke-test explicit canonical relationship",
            },
        },
    )

    _, home = json_request("GET", "/v1/graph/home?max_nodes=120")
    home_nodes = {entity_key(node["entity_type"], node["id"]): node for node in home["nodes"]}
    assert entity_key("project", project["id"]) in home_nodes, home
    assert entity_key("task", task["id"]) in home_nodes, home

    structural = next(
        edge
        for edge in home["edges"]
        if edge["source"]["entity_type"] == "task"
        and edge["source"]["entity_id"] == task["id"]
        and edge["target"]["entity_type"] == "project"
        and edge["target"]["entity_id"] == project["id"]
        and edge["relation"] == "belongs_to"
    )
    assert structural["provenance"] == "canonical_fk", structural
    assert structural["explanation"] == "Canonical project scope", structural

    explicit = next(edge for edge in home["edges"] if edge["id"] == relationship["id"])
    assert explicit["provenance"] == "canonical_relationship", explicit
    assert explicit["explanation"] == "Smoke-test explicit canonical relationship", explicit
    assert abs(float(explicit["strength"]) - 0.81) < 0.0001, explicit

    _, neighborhood = json_request(
        "GET",
        f"/v1/graph/neighborhood/project/{project['id']}?depth=1&max_nodes=40",
    )
    assert neighborhood["context"]["mode"] == "neighborhood", neighborhood
    assert neighborhood["context"]["focus"]["entity_id"] == project["id"], neighborhood
    assert any(node["id"] == task["id"] and node["entity_type"] == "task" for node in neighborhood["nodes"]), neighborhood

    _, search = json_request("GET", "/v1/graph/search?q=Spatial%20Graph%20Smoke&limit=10")
    assert any(node["id"] == project["id"] and node["entity_type"] == "project" for node in search["nodes"]), search

    print("KAIRO canonical spatial graph projection smoke proof passed")


if __name__ == "__main__":
    main()
