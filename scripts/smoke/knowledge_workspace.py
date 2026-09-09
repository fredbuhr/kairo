#!/usr/bin/env python3
"""End-to-end proof for KAIRO's canonical Knowledge workspace read model."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

CORE = "http://localhost:8000"
INTERNAL = {"X-Kairo-Internal-Token": "CHANGE_ME_INTERNAL_TOKEN"}


def json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {**(headers or {})}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read().decode("utf-8"))
    if status != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {body}")
    return status, body


def upload_text_asset(project_id: str) -> dict[str, Any]:
    boundary = "----kairo-knowledge-smoke-boundary"
    content = b"Canonical source object for the KAIRO Knowledge workspace smoke proof."
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"project_id\"\r\n\r\n{project_id}\r\n".encode(),
        (
            f"--{boundary}\r\n"
            "Content-Disposition: form-data; name=\"file\"; filename=\"knowledge-smoke.txt\"\r\n"
            "Content-Type: text/plain\r\n\r\n"
        ).encode()
        + content
        + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        CORE + "/v1/assets",
        data=b"".join(parts),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read().decode("utf-8"))
    if status != 201:
        raise AssertionError(f"POST /v1/assets: expected 201, got {status}: {body}")
    return body


def complete_version(version_id: str, source_sha256: str, marker: str) -> None:
    json_request(
        "POST",
        f"/internal/v1/documents/versions/{version_id}/complete",
        headers=INTERNAL,
        payload={
            "parser": "knowledge-smoke",
            "parser_version": "1",
            "source_sha256": source_sha256,
            "chunks": [
                {
                    "text": f"KAIRO canonical knowledge passage containing {marker} for deterministic retrieval.",
                    "metadata": {"fixture": True, "marker": marker},
                },
                {
                    "text": "A second passage proves that chunk order and version provenance remain visible.",
                    "metadata": {"fixture": True},
                },
            ],
            "metadata": {"fixture": "knowledge-workspace"},
        },
    )


def wait_ready() -> None:
    deadline = time.time() + 90
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            _, body = json_request("GET", "/health/ready")
            if body["status"] == "ready":
                return
        except Exception as exc:  # noqa: BLE001 - smoke test reports final readiness failure
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
            "name": "Knowledge Smoke Project",
            "status": "active",
            "summary": "Project used to prove canonical document retrieval.",
        },
    )
    asset = upload_text_asset(project["id"])

    _, run = json_request(
        "POST",
        "/v1/documents",
        expected=202,
        payload={"asset_id": asset["id"], "title": "Knowledge Smoke Document"},
    )
    document = run["document"]
    version_one = run["version"]
    assert document["project_id"] == project["id"], run
    assert version_one["generation"] == 1, run

    complete_version(version_one["id"], asset["sha256"], "OBSIDIAN-ALPHA")

    _, documents = json_request("GET", "/v1/documents")
    assert any(item["id"] == document["id"] and item["status"] == "ready" for item in documents), documents

    _, versions = json_request("GET", f"/v1/documents/{document['id']}/versions")
    assert versions[0]["generation"] == 1 and versions[0]["status"] == "completed", versions
    _, chunks = json_request("GET", f"/v1/document-versions/{version_one['id']}/chunks")
    assert len(chunks) == 2, chunks
    assert "OBSIDIAN-ALPHA" in chunks[0]["text"], chunks

    _, first_search = json_request("GET", "/v1/knowledge/search?q=OBSIDIAN-ALPHA&limit=10")
    assert first_search["query"] == "OBSIDIAN-ALPHA", first_search
    assert len(first_search["results"]) == 1, first_search
    hit = first_search["results"][0]
    assert hit["document_id"] == document["id"], hit
    assert hit["version_id"] == version_one["id"], hit
    assert hit["generation"] == 1, hit
    assert "OBSIDIAN-ALPHA" in hit["excerpt"], hit

    _, rerun = json_request(
        "POST",
        f"/v1/documents/{document['id']}/reingest",
        expected=202,
    )
    version_two = rerun["version"]
    assert version_two["generation"] == 2, rerun
    complete_version(version_two["id"], asset["sha256"], "VERDANT-BETA")

    # Retrieval is deliberately scoped to the newest completed canonical generation.
    _, stale_search = json_request("GET", "/v1/knowledge/search?q=OBSIDIAN-ALPHA&limit=10")
    assert stale_search["results"] == [], stale_search
    _, current_search = json_request("GET", "/v1/knowledge/search?q=VERDANT-BETA&limit=10")
    assert len(current_search["results"]) == 1, current_search
    current = current_search["results"][0]
    assert current["version_id"] == version_two["id"], current
    assert current["generation"] == 2, current

    print("KAIRO canonical Knowledge workspace smoke proof passed")


if __name__ == "__main__":
    main()
