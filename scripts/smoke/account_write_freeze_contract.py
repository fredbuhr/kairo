#!/usr/bin/env python3
"""Fail fast if the local account write freeze stops guarding public mutations."""

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
    model = text("services/core/src/kairo_core/account_lifecycle_models.py")
    migration = text("services/core/migrations/versions/0021_account_write_freeze.py")
    router = text("services/core/src/kairo_core/account_freeze.py")
    main_py = text("services/core/src/kairo_core/main.py")
    keycloak = text("services/core/src/kairo_core/keycloak_management.py")

    require(model, 'class AccountWriteFreeze(Base):', "write-freeze model")
    require(model, '__tablename__ = "account_write_freezes"', "write-freeze table")
    require(model, "keycloak_subject: Mapped[str]", "subject primary key")
    require(model, "operation_id: Mapped[uuid.UUID]", "freeze operation identity")

    require(migration, 'revision = "0021_account_write_freeze"', "migration revision")
    require(migration, 'down_revision = "0020_outbox_jetstream_receipts"', "migration chain")
    require(migration, 'sa.PrimaryKeyConstraint("keycloak_subject"', "one freeze per subject")
    require(migration, 'sa.UniqueConstraint("operation_id"', "unique freeze operation id")

    require(router, 'Literal["FREEZE_ACCOUNT_WRITES"]', "typed freeze confirmation")
    require(router, 'Literal["UNFREEZE_ACCOUNT_WRITES"]', "typed unfreeze confirmation")
    require(router, '"/v1/account/evidence/retention/apply"', "bounded evidence cleanup while frozen")
    require(router, '"/v1/account/derived-memory/purge"', "bounded memory cleanup while frozen")
    require(router, "return await get_account_write_freeze(session, subject) is not None", "canonical freeze lookup")
    require(router, 'event_type="account.write_frozen"', "freeze evidence event")
    require(router, 'event_type="account.write_unfrozen"', "unfreeze evidence event")
    forbid(router, "keycloak_identity_manager", "provider disable coupled directly to reversible local freeze")

    require(main_py, "account_writes_frozen", "public perimeter freeze lookup")
    require(main_py, "frozen_public_write_allowed", "explicit lifecycle write allow-list")
    require(main_py, 'method.upper() in {"GET", "HEAD", "OPTIONS"}', "read-only requests remain available")
    require(main_py, "status.HTTP_423_LOCKED", "frozen public mutation response")
    require(main_py, '"code": "account_write_frozen"', "stable frozen response code")
    require(main_py, "app.include_router(account_freeze_router)", "freeze router registration")
    require(main_py, 'not request.url.path.startswith("/v1/")', "internal routes remain outside public perimeter")

    # The Keycloak adapter stays separate. Local freeze is the protection against already-issued
    # bearer tokens; provider mutation is a later durable lifecycle phase.
    require(keycloak, "already-issued", "Keycloak disable token-lifetime warning")
    forbid(main_py, "disable_identity(", "Keycloak disable inside generic request perimeter")
    forbid(main_py, "delete_identity(", "Keycloak delete inside generic request perimeter")

    print("KAIRO account write-freeze contract passed")


if __name__ == "__main__":
    main()
