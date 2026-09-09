#!/usr/bin/env python3
"""Prove deployment diagnostics are admin-only while normal KAIRO users remain authenticated."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CORE = os.getenv("KAIRO_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "kairo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "kairo-web")
ADMIN_USER = os.getenv("KEYCLOAK_DEV_USERNAME", "kairo-dev")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_DEV_PASSWORD", "kairo-dev")
USER = os.getenv("KEYCLOAK_ALT_USERNAME", "kairo-alt")
USER_PASSWORD = os.getenv("KEYCLOAK_ALT_PASSWORD", "kairo-alt")


def access_token(username: str, password: str) -> str:
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data=form,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = str(payload.get("access_token") or "")
    if not token:
        raise AssertionError(f"Keycloak did not return a token for {username}")
    return token


def request_json(path: str, token: str, expected: int) -> Any:
    request = urllib.request.Request(
        CORE + path,
        method="GET",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status_code = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw = exc.read().decode("utf-8")
    payload = json.loads(raw) if raw else None
    if status_code != expected:
        raise AssertionError(f"GET {path}: expected {expected}, got {status_code}: {payload!r}")
    return payload


def main() -> None:
    admin_token = access_token(ADMIN_USER, ADMIN_PASSWORD)
    user_token = access_token(USER, USER_PASSWORD)

    for path in ("/v1/system/components", "/v1/system/architecture", "/v1/system/outbox"):
        admin_payload = request_json(path, admin_token, 200)
        assert admin_payload is not None, (path, admin_payload)
        denied = request_json(path, user_token, 403)
        assert denied.get("detail") == "KAIRO admin role required", (path, denied)

    print("KAIRO deployment diagnostics admin-only visibility proof passed")


if __name__ == "__main__":
    main()
