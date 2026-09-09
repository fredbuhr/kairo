#!/usr/bin/env python3
"""Fail fast if disaster recovery can bypass KAIRO's erasure-resurrection guard."""

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


def before(source: str, first: str, second: str, label: str) -> None:
    first_index = source.find(first)
    second_index = source.find(second)
    if first_index < 0 or second_index < 0 or first_index >= second_index:
        raise AssertionError(f"Invalid ordering for {label}: {first!r} must precede {second!r}")


def main() -> None:
    restore = text("scripts/ops/restore.sh")
    backup = text("scripts/ops/backup.sh")
    gitignore = text(".gitignore")
    lifecycle = text("services/core/src/kairo_core/account_lifecycle.py")
    decision = text(
        "docs/decisions/ADR-049-backup-restore-is-guarded-by-a-monotonic-erasure-ledger.md"
    )

    require(gitignore, ".kairo-erasure-ledger/", "local erasure ledger outside source control")
    require(restore, 'KAIRO_ENV_VALUE="${KAIRO_ENV:-$(env_file_value KAIRO_ENV)}"', "environment-aware production detection")
    forbid(restore, 'if [[ "$OVERLAY" == *production*', "overlay-name production inference")
    require(restore, "KAIRO_ERASURE_LEDGER_PATH", "external erasure ledger configuration")
    require(restore, '.kairo-erasure-ledger/tombstones.jsonl', "safe local ledger fallback")
    require(restore, 'if [[ "$KAIRO_ENV_VALUE" == "production" && ! -f "$ERASURE_LEDGER_PATH" ]]', "production missing-ledger refusal")
    require(restore, 'if [[ -s "$ERASURE_LEDGER_PATH" ]]', "non-empty ledger refusal")
    require(restore, "no verified post-restore tombstone reconciler", "truthful reconciliation blocker")

    # Both privacy guards must run before Restic even materializes the old snapshot, and therefore
    # before the volume restore helper can mutate PostgreSQL/NATS/Seaweed/OpenBao.
    before(
        restore,
        'if [[ "$KAIRO_ENV_VALUE" == "production" && ! -f "$ERASURE_LEDGER_PATH" ]]',
        'ops run --rm restic restore "$SNAPSHOT"',
        "production ledger availability before Restic restore",
    )
    before(
        restore,
        'if [[ -s "$ERASURE_LEDGER_PATH" ]]',
        'ops run --rm restic restore "$SNAPSHOT"',
        "tombstone refusal before Restic restore",
    )
    before(
        restore,
        'if [[ -s "$ERASURE_LEDGER_PATH" ]]',
        "ops run --rm volume-restore",
        "tombstone refusal before durable volume mutation",
    )

    # The monotonic guard must never roll back with the state it protects.
    forbid(backup, ".kairo-erasure-ledger", "erasure ledger in state backup")
    forbid(backup, "KAIRO_ERASURE_LEDGER_PATH", "configured erasure ledger in state backup")
    require(backup, "/data/postgres", "canonical PostgreSQL backup")
    require(backup, "/data/nats", "NATS backup")
    require(backup, "/data/seaweed", "SeaweedFS backup")
    require(backup, "/data/openbao", "OpenBao backup")

    require(lifecycle, 'code="backup_retention_policy_not_verified"', "backup remains complete-erasure blocker")
    require(decision, "monotonic erasure-ledger boundary", "monotonic external ledger decision")
    require(decision, "fail-closed restore behavior", "documented restore refusal")
    require(decision, "does not by itself erase historical encrypted backup bytes", "no false backup-erasure claim")

    print("KAIRO restore-after-erasure guard contract passed")


if __name__ == "__main__":
    main()
