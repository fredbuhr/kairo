#!/usr/bin/env python3
"""Fail fast if account evidence retention loses its cross-store/privacy invariants."""

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
    evidence = text("services/core/src/kairo_core/account_evidence.py")
    lifecycle = text("services/core/src/kairo_core/account_lifecycle.py")
    main_py = text("services/core/src/kairo_core/main.py")
    decision = text(
        "docs/decisions/ADR-047-account-evidence-retention-minimizes-audit-and-clears-outbox-transport.md"
    )

    require(main_py, "from .account_evidence import router as account_evidence_router", "retention router import")
    require(main_py, "app.include_router(account_evidence_router)", "retention router registration")

    require(evidence, 'Literal["MINIMIZE_ACCOUNT_EVIDENCE"]', "explicit destructive confirmation")
    require(evidence, "_RETENTION_BATCH_LIMIT = 250", "bounded retention batch")
    require(evidence, "_TRANSPORT_EXPIRY_GRACE_SECONDS = 300", "historical expiry grace")
    for blocker in (
        "active_tasks",
        "active_workflows",
        "pending_approvals",
        "active_automation_invocations",
        "active_tool_invocations",
    ):
        require(evidence, f'"{blocker}"', f"active-work blocker {blocker}")

    require(evidence, "OutboxEvent.published_at.is_(None)", "unpublished Outbox refusal")
    require(evidence, "partial_jetstream_receipt", "partial receipt refusal")
    require(evidence, "await js.stream_info(settings.nats_domain_stream)", "live JetStream contract read")
    require(evidence, "actual_age > expected_age", "bounded max-age refusal")
    require(evidence, "list(config.subjects or []) != [DOMAIN_SUBJECT]", "domain subject contract")
    require(evidence, "await js.delete_msg(", "exact mapped JetStream deletion")
    require(evidence, "except NotFoundError:", "idempotent already-absent message handling")
    require(evidence, "published_at > expiry_cutoff", "historical unreceipted max-age gate")
    require(evidence, "delete(OutboxEvent)", "PostgreSQL Outbox deletion after transport reconciliation")

    require(evidence, "record.keycloak_subject = None", "subject-owned Audit detachment")
    require(evidence, "record.actor_id = None", "Audit actor removal")
    require(evidence, 'record.resource_id = "erased"', "personal resource id minimization")
    require(evidence, "record.correlation_id = uuid.uuid4()", "correlation unlinking")
    require(evidence, "record.idempotency_key = None", "idempotency identifier removal")
    require(evidence, "record.request_json = {}", "personal request payload removal")
    require(evidence, 'record.result_json = {"retention": "minimized"}', "minimal retained Audit marker")
    require(evidence, "_redact_subject_json", "shared control-plane subject redaction")

    require(evidence, 'action="account.evidence.retention.apply"', "neutral destructive receipt")
    require(evidence, "keycloak_subject=None", "neutral receipt owner absence")
    require(evidence, "actor_id=None", "neutral receipt actor absence")
    forbid(evidence, "sha256(principal.subject", "stable erased-subject hash")
    forbid(evidence, "hmac", "stable erased-subject HMAC")

    require(lifecycle, "retention_action_available: bool = True", "account inventory retention availability")
    require(lifecycle, 'code="audit_outbox_retention_required"', "conditional erasure blocker")
    require(lifecycle, "if evidence_count:", "evidence blocker disappears when clean")
    forbid(lifecycle, "audit_outbox_retention_policy_not_applied", "obsolete unimplemented-policy blocker")

    require(decision, "Outbox transport first", "documented transport-before-database rule")
    require(decision, "Audit minimization", "documented Audit minimization rule")
    require(decision, "Shared administrative Audit", "documented shared actor redaction rule")

    print("KAIRO account evidence retention contract passed")


if __name__ == "__main__":
    main()
