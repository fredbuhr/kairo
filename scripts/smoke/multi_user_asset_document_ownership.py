#!/usr/bin/env python3
"""Prove first-class Asset/Document ownership with two real Keycloak identities."""

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
    body = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        }
    ).encode()
    request = urllib.request.Request(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data=body,
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
            code = response.status
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read().decode()
    body = json.loads(raw) if raw else None
    if code != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {code}: {body!r}")
    return body


def upload_asset(
    bearer: str,
    *,
    filename: str,
    content: bytes,
    project_id: str | None = None,
    expected: int = 201,
) -> Any:
    boundary = f"kairo-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def field(name: str, value: str) -> None:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )

    if project_id is not None:
        field("project_id", project_id)
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: text/plain\r\n\r\n",
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        CORE + "/v1/assets",
        data=b"".join(chunks),
        method="POST",
        headers={
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            code = response.status
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read().decode()
    body = json.loads(raw) if raw else None
    if code != expected:
        raise AssertionError(f"POST /v1/assets: expected {expected}, got {code}: {body!r}")
    return body


def ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["id"]) for row in rows}


def main() -> None:
    a = token(USER_A, PASSWORD_A)
    b = token(USER_B, PASSWORD_B)
    nonce = uuid.uuid4().hex[:10]

    project_a = request_json(
        "POST",
        "/v1/projects",
        a,
        expected=201,
        payload={"name": f"Asset owner A {nonce}", "status": "active", "summary": None, "parent_id": None},
    )
    project_b = request_json(
        "POST",
        "/v1/projects",
        b,
        expected=201,
        payload={"name": f"Asset owner B {nonce}", "status": "active", "summary": None, "parent_id": None},
    )

    asset_a = upload_asset(
        a,
        filename=f"a-{nonce}.txt",
        content=f"private asset A {nonce}".encode(),
        project_id=project_a["id"],
    )
    asset_b = upload_asset(
        b,
        filename=f"b-{nonce}.txt",
        content=f"private asset B {nonce}".encode(),
        project_id=project_b["id"],
    )

    # A foreign Project is rejected before an Asset can be attached to it.
    upload_asset(
        a,
        filename="cross-project.txt",
        content=b"must not persist",
        project_id=project_b["id"],
        expected=404,
    )

    assets_a = request_json("GET", "/v1/assets", a)
    assets_b = request_json("GET", "/v1/assets", b)
    assert asset_a["id"] in ids(assets_a) and asset_b["id"] not in ids(assets_a), assets_a
    assert asset_b["id"] in ids(assets_b) and asset_a["id"] not in ids(assets_b), assets_b
    request_json("GET", f"/v1/assets/{asset_b['id']}", a, expected=404)
    request_json("GET", f"/v1/assets/{asset_a['id']}", b, expected=404)
    request_json("GET", f"/v1/assets/{asset_b['id']}/content", a, expected=404)

    # A foreign Asset cannot become the source of another user's Document.
    request_json(
        "POST",
        "/v1/documents",
        a,
        payload={"asset_id": asset_b["id"], "title": "Cross-owner document"},
        expected=404,
    )

    document_a = request_json(
        "POST",
        "/v1/documents",
        a,
        payload={"asset_id": asset_a["id"], "title": f"Document A {nonce}"},
        expected=202,
    )["document"]
    document_b = request_json(
        "POST",
        "/v1/documents",
        b,
        payload={"asset_id": asset_b["id"], "title": f"Document B {nonce}"},
        expected=202,
    )["document"]

    documents_a = request_json("GET", "/v1/documents", a)
    documents_b = request_json("GET", "/v1/documents", b)
    assert document_a["id"] in ids(documents_a) and document_b["id"] not in ids(documents_a), documents_a
    assert document_b["id"] in ids(documents_b) and document_a["id"] not in ids(documents_b), documents_b
    request_json("GET", f"/v1/documents/{document_b['id']}", a, expected=404)
    request_json("GET", f"/v1/documents/{document_a['id']}", b, expected=404)
    request_json("GET", f"/v1/documents/{document_b['id']}/versions", a, expected=404)

    print("KAIRO Asset/Document two-user ownership proof passed")


if __name__ == "__main__":
    main()
