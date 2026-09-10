from __future__ import annotations

import json
import time
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"


def request(method: str, path: str, payload: object | None = None, *, headers: dict[str, str] | None = None, body: bytes | None = None):
    merged = {"Accept": "application/json", **(headers or {})}
    data = body
    if payload is not None:
        data = json.dumps(payload).encode()
        merged["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=merged, method=method)
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def wait_ready() -> None:
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            request("GET", "/health/ready")
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("KAIRO Core did not become ready")


def multipart_file(
    filename: str,
    content: bytes,
    content_type: str,
    project_id: str | None = None,
) -> tuple[bytes, str]:
    boundary = "----kairo-doc-" + uuid.uuid4().hex
    parts: list[bytes] = []
    if project_id is not None:
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"project_id\"\r\n\r\n{project_id}\r\n".encode()
        )
    parts.extend(
        [
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
            + content
            + b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(parts), boundary


def upload_text_asset(filename: str, source: bytes, project_id: str | None = None) -> dict:
    body, boundary = multipart_file(filename, source, "text/plain", project_id)
    return request(
        "POST",
        "/v1/assets",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        body=body,
    )


def wait_version(document_id: str, generation: int) -> dict:
    deadline = time.time() + 120
    latest = None
    while time.time() < deadline:
        versions = request("GET", f"/v1/documents/{document_id}/versions")
        latest = next((item for item in versions if item["generation"] == generation), None)
        if latest and latest["status"] == "completed":
            return latest
        if latest and latest["status"] == "failed":
            raise AssertionError(latest)
        time.sleep(1)
    raise AssertionError({"generation": generation, "latest": latest})


def main() -> None:
    wait_ready()
    source = (
        "KAIRO document ingestion proof.\n\n"
        "This first paragraph establishes canonical provenance.\n\n"
        "This second paragraph proves deterministic chunk extraction without a model call."
    ).encode()

    project = request("POST", "/v1/projects", {"name": "Document ingestion proof"})
    asset = upload_text_asset("proof.txt", source, project["id"])
    run = request("POST", "/v1/documents", {"asset_id": asset["id"], "title": "Proof document"})
    document = run["document"]
    assert document["asset_id"] == asset["id"], run
    assert document["project_id"] == project["id"], run
    assert document["source_sha256"] == asset["sha256"], run

    version1 = wait_version(document["id"], 1)
    chunks1 = request("GET", f"/v1/document-versions/{version1['id']}/chunks")
    assert version1["chunk_count"] == len(chunks1) > 0, (version1, chunks1)
    assert all(chunk["content_sha256"] for chunk in chunks1), chunks1
    first_ids = [chunk["id"] for chunk in chunks1]
    first_text = [chunk["text"] for chunk in chunks1]

    second_run = request("POST", f"/v1/documents/{document['id']}/reingest")
    assert second_run["version"]["generation"] == 2, second_run
    version2 = wait_version(document["id"], 2)
    chunks2 = request("GET", f"/v1/document-versions/{version2['id']}/chunks")
    assert [chunk["text"] for chunk in chunks2] == first_text, chunks2
    assert [chunk["id"] for chunk in chunks2] != first_ids, chunks2

    original = request("GET", f"/v1/assets/{asset['id']}")
    assert original["sha256"] == asset["sha256"], original
    versions = request("GET", f"/v1/documents/{document['id']}/versions")
    assert [item["generation"] for item in versions[:2]] == [2, 1], versions

    # An uploaded asset is allowed to be unscoped, but document Tasks are not.
    # Prove the canonical document explicitly falls back to the owner-scoped
    # KAIRO Documents workspace and that Temporal ingestion still completes.
    unscoped_asset = upload_text_asset("unscoped.txt", b"Unscoped assets still need a durable document workspace.")
    assert unscoped_asset["project_id"] is None, unscoped_asset
    unscoped_run = request(
        "POST",
        "/v1/documents",
        {"asset_id": unscoped_asset["id"], "title": "Unscoped proof"},
    )
    unscoped_document = unscoped_run["document"]
    owner_subject = str((unscoped_document.get("metadata_json") or {}).get("owner_subject") or "").strip()
    assert owner_subject, unscoped_run
    expected_documents_project_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:project:documents:subject:{owner_subject}")
    )
    assert unscoped_document["project_id"] == expected_documents_project_id, unscoped_run
    projects = request("GET", "/v1/projects")
    documents_project = next(
        (item for item in projects if item["id"] == expected_documents_project_id),
        None,
    )
    assert documents_project is not None, projects
    assert documents_project["name"] == "KAIRO Documents", documents_project
    unscoped_version = wait_version(unscoped_document["id"], 1)
    assert unscoped_version["status"] == "completed", unscoped_version

    print("document ingestion proof passed")


if __name__ == "__main__":
    main()
