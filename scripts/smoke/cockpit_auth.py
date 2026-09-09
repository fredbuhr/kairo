#!/usr/bin/env python3
"""Prove the authenticated public API perimeter used by KAIRO Web/Desktop.

This smoke test deliberately exercises routes that historically had no endpoint-local auth dependency
(Graph and the early Project surface). The `/v1` perimeter must reject anonymous/invalid requests,
accept the real Keycloak bearer token, and keep CORS preflights/error responses browser-readable.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CORE = os.getenv("KAIRO_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "kairo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "kairo-web")
USERNAME = os.getenv("KEYCLOAK_DEV_USERNAME", "kairo-dev")
PASSWORD = os.getenv("KEYCLOAK_DEV_PASSWORD", "kairo-dev")
ORIGIN = "http://localhost:5173"


def request(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    expected: set[int] | None = None,
    timeout: float = 20.0,
) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.status
            payload = response.read()
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        payload = exc.read()
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
    allowed = expected or {200}
    if status_code not in allowed:
        raise AssertionError(
            f"{method} {url} returned {status_code}, expected {sorted(allowed)}: {payload[:1000]!r}"
        )
    return status_code, payload, response_headers


def wait_ready(url: str, label: str, *, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status_code, _, _ = request("GET", url, expected={200, 503})
            if status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001 - smoke harness keeps the last readiness error
            last = exc
        time.sleep(1.0)
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
    _, raw, _ = request(
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


def core_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    origin: str | None = None,
    expected: set[int] | None = None,
) -> tuple[int, Any, dict[str, str]]:
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if origin:
        headers["Origin"] = origin
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    status_code, raw, response_headers = request(
        method,
        f"{CORE}{path}",
        body=body,
        headers=headers,
        expected=expected,
    )
    parsed = json.loads(raw.decode()) if raw else None
    return status_code, parsed, response_headers


def main() -> None:
    wait_ready(f"{CORE}/health/ready", "KAIRO Core")
    wait_ready(
        f"{KEYCLOAK}/realms/{REALM}/.well-known/openid-configuration",
        "Keycloak realm",
    )

    # Health stays public for orchestrators, but the canonical Cockpit world model must not.
    status_code, _, _ = request("GET", f"{CORE}/health/live", expected={200})
    assert status_code == 200

    anonymous_status, anonymous, anonymous_headers = core_json(
        "GET",
        "/v1/graph/home?max_nodes=12",
        origin=ORIGIN,
        expected={401},
    )
    assert anonymous_status == 401, anonymous
    assert anonymous.get("detail") == "Bearer token required", anonymous
    assert anonymous_headers.get("www-authenticate") == "Bearer", anonymous_headers
    assert anonymous_headers.get("access-control-allow-origin") == ORIGIN, anonymous_headers

    invalid_status, invalid, _ = core_json(
        "GET",
        "/v1/projects",
        token="not-a-valid-jwt",
        expected={401},
    )
    assert invalid_status == 401, invalid
    assert invalid.get("detail") == "Invalid or unverifiable Keycloak token", invalid

    # Browser preflight cannot carry the bearer token and must therefore pass the auth perimeter.
    preflight_status, _, preflight_headers = request(
        "OPTIONS",
        f"{CORE}/v1/projects",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
        expected={200},
    )
    assert preflight_status == 200
    assert preflight_headers.get("access-control-allow-origin") == ORIGIN, preflight_headers
    assert "authorization" in preflight_headers.get("access-control-allow-headers", "").lower(), preflight_headers

    token = access_token()

    graph_status, graph, _ = core_json(
        "GET",
        "/v1/graph/home?max_nodes=12",
        token=token,
        expected={200},
    )
    assert graph_status == 200, graph
    assert isinstance(graph, dict) and isinstance(graph.get("nodes"), list), graph

    architecture_status, architecture, _ = core_json(
        "GET",
        "/v1/system/architecture",
        token=token,
        expected={200},
    )
    assert architecture_status == 200, architecture
    assert architecture.get("public_api_authentication") == "fail-closed-v1-bearer-perimeter", architecture

    # Prove one of the original direct main.py domain routes also carries the authenticated actor.
    _, project, _ = core_json(
        "POST",
        "/v1/projects",
        token=token,
        payload={
            "name": "Authenticated Cockpit Fixture",
            "status": "active",
            "summary": "Public API bearer-perimeter smoke proof",
            "parent_id": None,
        },
        expected={201},
    )
    assert project.get("id"), project

    _, projects, _ = core_json("GET", "/v1/projects", token=token, expected={200})
    assert any(row.get("id") == project["id"] for row in projects), projects

    # Anonymous mutation remains denied even after a valid user created canonical state.
    denied_status, denied, _ = core_json(
        "POST",
        "/v1/projects",
        payload={
            "name": "Must Not Exist",
            "status": "active",
            "summary": None,
            "parent_id": None,
        },
        expected={401},
    )
    assert denied_status == 401, denied

    print("KAIRO Cockpit bearer perimeter, CORS and authenticated canonical route proof passed")


if __name__ == "__main__":
    main()
