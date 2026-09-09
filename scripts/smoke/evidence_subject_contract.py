#!/usr/bin/env python3
"""Fail fast if Audit/Outbox data-subject ownership loses its schema or construction boundaries."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(source: str, needle: str, label: str) -> None:
    if needle not in source:
        raise AssertionError(f"Missing {label}: {needle!r}")


def main() -> None:
    models = text("services/core/src/kairo_core/models.py")
    events = text("services/core/src/kairo_core/events.py")
    resolver = text("services/core/src/kairo_core/event_ownership.py")
    command_models = text("services/core/src/kairo_core/command_models.py")
    migration = text("services/core/migrations/versions/0019_audit_outbox_data_subject.py")
    graph_activity = text("services/core/src/kairo_core/graph_activity.py")
    lifecycle = text("services/core/src/kairo_core/account_lifecycle.py")

    require(models, "class AuditRecord", "Audit model")
    require(models, "keycloak_subject: Mapped[str | None]", "nullable data-subject field")
    require(models, 'Index("ix_audit_subject_created"', "Audit subject index")
    require(models, 'Index("ix_outbox_subject_created"', "Outbox subject index")
    require(models, 'Index("ix_audit_user_actor_created"', "shared actor-reference index")

    require(events, "resolve_data_subject", "central canonical owner resolver")
    require(events, "owner = await resolve_data_subject(session, aggregate_type, aggregate_id)", "Outbox resolver call")
    require(events, "owner = await resolve_data_subject(session, resource_type, resource_id)", "Audit resolver call")
    require(events, "keycloak_subject=owner", "owner write")

    require(resolver, "_SHARED_CONTROL_PLANE", "shared control-plane allow-list")
    require(resolver, '"tool_server"', "shared ToolServer classification")
    require(resolver, '"tool_definition"', "shared ToolDefinition classification")
    for user_kind in (
        "project",
        "task",
        "conversation_message",
        "document",
        "automation_invocation",
        "finance_connector",
        "tool_invocation",
    ):
        require(resolver, f'kind == "{user_kind}"', f"resolver for {user_kind}")

    # ConversationMessage creates its transactional event from a synchronous SQLAlchemy listener,
    # bypassing the async helper. It must resolve the Conversation owner before direct insertion.
    require(command_models, "owner_subject = connection.execute", "direct listener owner lookup")
    require(command_models, "keycloak_subject=owner_subject", "direct listener owner write")

    require(migration, 'revision = "0019_audit_outbox_data_subject"', "migration revision")
    require(migration, 'op.add_column("audit_records"', "Audit owner migration")
    require(migration, 'op.add_column("outbox_events"', "Outbox owner migration")
    require(migration, "WITH owners(kind, entity_id, keycloak_subject)", "historical canonical backfill")

    # Live graph activity must not load installation-wide Outbox rows and then filter them in Python.
    require(
        graph_activity,
        "OutboxEvent.keycloak_subject == principal.subject",
        "subject-first Graph SSE query",
    )
    require(
        graph_activity,
        "OutboxEvent.keycloak_subject == subject",
        "subject-scoped Last-Event-ID cursor",
    )

    require(lifecycle, "class EvidenceInventory", "account evidence inventory")
    require(lifecycle, "shared_audit_actor_references", "shared audit actor retention accounting")
    require(lifecycle, "audit_outbox_retention_policy_not_applied", "truthful retention blocker")

    print("KAIRO Audit/Outbox data-subject contract passed")


if __name__ == "__main__":
    main()
