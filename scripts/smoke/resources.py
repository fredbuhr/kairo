from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

CORE = os.getenv("KAIRO_CORE_HTTP", "http://127.0.0.1:8000").rstrip("/")
KEYCLOAK = os.getenv("KEYCLOAK_HTTP", "http://127.0.0.1:8081").rstrip("/")
OPENBAO = os.getenv("OPENBAO_HTTP", "http://127.0.0.1:8200").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "kairo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "kairo-web")
USERNAME = os.getenv("KEYCLOAK_DEV_USERNAME", "kairo-dev")
PASSWORD = os.getenv("KEYCLOAK_DEV_PASSWORD", "kairo-dev")
OPENBAO_TOKEN = os.getenv("OPENBAO_DEV_TOKEN", "CHANGE_ME_OPENBAO")
SECRET_PROOF = "kairo-ci-secret-value-must-never-leak"


def request(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    expected: set[int] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            status_code = response.status
            payload = response.read()
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        payload = exc.read()
        response_headers = dict(exc.headers.items())
    allowed = expected or {200}
    if status_code not in allowed:
        raise AssertionError(
            f"{method} {url} returned {status_code}, expected {sorted(allowed)}: {payload[:1000]!r}"
        )
    return status_code, payload, response_headers


def json_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    expected: set[int] | None = None,
) -> tuple[int, dict, bytes]:
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    status_code, raw, _ = request(
        method, f"{CORE}{path}", body=body, headers=headers, expected=expected
    )
    parsed = json.loads(raw.decode()) if raw else {}
    return status_code, parsed, raw


def wait_for(url: str, label: str, *, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status_code, _, _ = request("GET", url, expected={200, 503})
            if status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001 - smoke harness records the last failure
            last = exc
        time.sleep(1.5)
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


def token_subject(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload).decode())
    return str(claims["sub"])


def seed_openbao() -> None:
    body = json.dumps(
        {"data": {"api_key": SECRET_PROOF, "region": "integration-test"}}
    ).encode()
    request(
        "POST",
        f"{OPENBAO}/v1/secret/data/kairo/integration",
        body=body,
        headers={
            "Content-Type": "application/json",
            "X-Vault-Token": OPENBAO_TOKEN,
        },
        expected={200, 204},
    )


def multipart_file(field: str, filename: str, content_type: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----kairo-{uuid.uuid4().hex}"
    chunks = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), boundary


def main() -> int:
    wait_for(f"{KEYCLOAK}/realms/{REALM}/.well-known/openid-configuration", "Keycloak realm")
    wait_for(f"{CORE}/health/trust", "KAIRO trust boundary")

    # Sensitive endpoints are closed by default.
    json_request(
        "POST",
        "/v1/devices",
        payload={"device_key": "ci-device", "name": "CI", "platform": "linux"},
        expected={401},
    )

    token = access_token()
    subject = token_subject(token)

    _, device, _ = json_request(
        "POST",
        "/v1/devices",
        token=token,
        payload={
            "device_key": "ci-device",
            "name": "CI runner",
            "platform": "linux",
            "capabilities": {"filesystem": False, "microphone": False},
        },
        expected={201},
    )
    assert device["keycloak_subject"] == subject
    device_id = device["id"]

    json_request(
        "POST",
        "/v1/devices",
        token=token,
        payload={"device_key": "ci-device", "name": "duplicate", "platform": "linux"},
        expected={409},
    )

    _, devices, _ = json_request("GET", "/v1/devices", token=token, expected={200})
    assert len(devices) == 1 and devices[0]["id"] == device_id

    seed_openbao()
    _, reference, reference_raw = json_request(
        "POST",
        "/v1/secret-references",
        token=token,
        payload={
            "name": "integration-proof",
            "provider_path": "secret/data/kairo/integration",
            "purpose": "prove OpenBao metadata boundary",
        },
        expected={201},
    )
    assert SECRET_PROOF.encode() not in reference_raw
    reference_id = reference["id"]

    _, secret_status, status_raw = json_request(
        "GET",
        f"/v1/secret-references/{reference_id}/status",
        token=token,
        expected={200},
    )
    assert secret_status["exists"] is True
    assert secret_status["keys"] == ["api_key", "region"]
    assert SECRET_PROOF.encode() not in status_raw

    proof = b"KAIRO SeaweedFS authenticated asset proof\n"
    multipart, boundary = multipart_file("file", "proof.txt", "text/plain", proof)
    _, asset_raw, _ = request(
        "POST",
        f"{CORE}/v1/assets",
        body=multipart,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        expected={201},
    )
    asset = json.loads(asset_raw.decode())
    assert asset["sha256"] == hashlib.sha256(proof).hexdigest()
    asset_id = asset["id"]

    _, downloaded, download_headers = request(
        "GET",
        f"{CORE}/v1/assets/{asset_id}/content",
        headers={"Authorization": f"Bearer {token}"},
        expected={200},
    )
    assert downloaded == proof
    assert download_headers.get("X-Content-SHA256") == hashlib.sha256(proof).hexdigest()

    request(
        "DELETE",
        f"{CORE}/v1/assets/{asset_id}",
        headers={"Authorization": f"Bearer {token}"},
        expected={204},
    )
    json_request("GET", f"/v1/assets/{asset_id}", token=token, expected={404})

    json_request(
        "DELETE", f"/v1/secret-references/{reference_id}", token=token, expected={204}
    )
    json_request("DELETE", f"/v1/devices/{device_id}", token=token, expected={204})

    print(
        "TRUST RESOURCE SMOKE PASSED: JWT subject ownership, OpenBao non-disclosure, "
        "and SeaweedFS asset round-trip are proven."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
