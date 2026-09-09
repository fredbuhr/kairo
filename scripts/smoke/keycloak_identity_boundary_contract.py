#!/usr/bin/env python3
"""Fail fast if Keycloak account lifecycle gains broad or public admin authority."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(source: str, needle: str, label: str) -> None:
    if needle not in source:
        raise AssertionError(f"Missing {label}: {needle!r}")


def forbid(source: str, needle: str, label: str) -> None:
    if needle in source:
        raise AssertionError(f"Forbidden {label}: {needle!r}")


def main() -> None:
    adapter = text("services/core/src/kairo_core/keycloak_management.py")
    config = text("services/core/src/kairo_core/config.py")
    env = text(".env.example")
    compose = text("compose.override.yaml")
    decision = text(
        "docs/decisions/ADR-048-keycloak-identity-management-is-a-separate-least-privilege-adapter.md"
    )

    require(config, 'keycloak_management_client_id: str = "kairo-identity-manager"', "dedicated management client id")
    require(config, 'keycloak_management_client_secret: str = ""', "management disabled by default")
    require(adapter, "self.client_id == settings.keycloak_client_id", "public client reuse refusal")
    require(adapter, '"grant_type": "client_credentials"', "client-credentials grant")
    require(adapter, "/admin/realms/", "Keycloak Admin REST user path")
    require(adapter, "quote(normalized, safe='')", "exact encoded subject target")
    require(adapter, "returned_id != subject", "returned user id verification")
    require(adapter, 'json={"enabled": False}', "bounded identity disable")
    require(adapter, "if verified.exists:", "identity delete verification")
    require(adapter, "if response.status_code not in {204, 404}", "idempotent delete status handling")

    forbid(adapter, "APIRouter", "public identity-management router")
    forbid(adapter, "KEYCLOAK_ADMIN", "bootstrap admin credential use")
    forbid(adapter, '"grant_type": "password"', "password grant")
    forbid(adapter, 'params={"username"', "username search target")
    forbid(adapter, 'params={"email"', "email search target")

    require(env, "KEYCLOAK_MANAGEMENT_CLIENT_ID=kairo-identity-manager", "deployment management client id")
    require(env, "KEYCLOAK_MANAGEMENT_CLIENT_SECRET=\n", "empty development management secret")
    require(compose, "KEYCLOAK_MANAGEMENT_CLIENT_ID: ${KEYCLOAK_MANAGEMENT_CLIENT_ID}", "Core management client id wiring")
    require(compose, "KEYCLOAK_MANAGEMENT_CLIENT_SECRET: ${KEYCLOAK_MANAGEMENT_CLIENT_SECRET}", "Core management secret wiring")
    forbid(compose, "KEYCLOAK_MANAGEMENT_CLIENT_SECRET: ${KEYCLOAK_ADMIN_PASSWORD}", "bootstrap admin reuse")

    require(decision, "Separate confidential workload identity", "least-privilege workload decision")
    require(decision, "No public self-lockout", "no premature public identity mutation")
    require(decision, "local write freeze", "local bearer-token freeze prerequisite")

    print("KAIRO Keycloak identity-management boundary contract passed")


if __name__ == "__main__":
    main()
