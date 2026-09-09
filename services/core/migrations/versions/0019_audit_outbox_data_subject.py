"""Add canonical data-subject addressing to audit and outbox evidence.

Revision ID: 0019_audit_outbox_data_subject
Revises: 0018_asset_document_ownership
Create Date: 2026-09-09

`keycloak_subject` identifies the owner of the user-world resource/event, not necessarily the actor.
Shared deployment/control-plane evidence stays NULL even when an administrator was the actor.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0019_audit_outbox_data_subject"
down_revision = "0018_asset_document_ownership"
branch_labels = None
depends_on = None


_OWNER_CTE = r"""
WITH owners(kind, entity_id, keycloak_subject) AS (
    SELECT 'project', p.id, p.keycloak_subject FROM projects p
    UNION ALL
    SELECT 'task', t.id, p.keycloak_subject
      FROM tasks t JOIN projects p ON p.id = t.project_id
    UNION ALL
    SELECT 'workflow_execution', w.id, p.keycloak_subject
      FROM workflow_executions w
      JOIN tasks t ON t.id = w.task_id
      JOIN projects p ON p.id = t.project_id
    UNION ALL
    SELECT 'artifact', a.id, p.keycloak_subject
      FROM artifacts a JOIN projects p ON p.id = a.project_id
    UNION ALL
    SELECT 'relationship', r.id, r.keycloak_subject FROM relationships r
    UNION ALL
    SELECT 'asset', a.id, a.keycloak_subject FROM assets a
    UNION ALL
    SELECT 'device', d.id, d.keycloak_subject FROM device_registrations d
    UNION ALL
    SELECT 'secret_reference', s.id, s.keycloak_subject FROM secret_references s
    UNION ALL
    SELECT 'conversation', c.id, c.subject_ref FROM conversations c WHERE c.subject_ref IS NOT NULL
    UNION ALL
    SELECT 'conversation_message', m.id, c.subject_ref
      FROM conversation_messages m
      JOIN conversations c ON c.id = m.conversation_id
     WHERE c.subject_ref IS NOT NULL
    UNION ALL
    SELECT 'command', cmd.id, c.subject_ref
      FROM commands cmd
      JOIN conversations c ON c.id = cmd.conversation_id
     WHERE c.subject_ref IS NOT NULL
    UNION ALL
    SELECT 'approval_request', a.id, p.keycloak_subject
      FROM approval_requests a
      JOIN tasks t ON t.id = a.task_id
      JOIN projects p ON p.id = t.project_id
    UNION ALL
    SELECT 'model_usage_record', m.id, p.keycloak_subject
      FROM model_usage_records m
      JOIN tasks t ON t.id = m.task_id
      JOIN projects p ON p.id = t.project_id
    UNION ALL
    SELECT 'document', d.id, d.keycloak_subject FROM documents d
    UNION ALL
    SELECT 'document_version', v.id, d.keycloak_subject
      FROM document_versions v JOIN documents d ON d.id = v.document_id
    UNION ALL
    SELECT 'document_chunk', ch.id, d.keycloak_subject
      FROM document_chunks ch
      JOIN document_versions v ON v.id = ch.document_version_id
      JOIN documents d ON d.id = v.document_id
    UNION ALL
    SELECT 'calendar_source', c.id, c.keycloak_subject FROM calendar_sources c
    UNION ALL
    SELECT 'external_calendar_event', e.id, c.keycloak_subject
      FROM external_calendar_events e JOIN calendar_sources c ON c.id = e.source_id
    UNION ALL
    SELECT 'automation', a.id, a.keycloak_subject FROM automation_definitions a
    UNION ALL
    SELECT 'automation_invocation', i.id, a.keycloak_subject
      FROM automation_invocations i
      JOIN automation_definitions a ON a.id = i.automation_id
    UNION ALL
    SELECT 'finance_source', f.id, f.keycloak_subject FROM finance_sources f
    UNION ALL
    SELECT 'finance_account', a.id, f.keycloak_subject
      FROM finance_accounts a JOIN finance_sources f ON f.id = a.source_id
    UNION ALL
    SELECT 'finance_position', pos.id, f.keycloak_subject
      FROM finance_positions pos
      JOIN finance_accounts a ON a.id = pos.account_id
      JOIN finance_sources f ON f.id = a.source_id
    UNION ALL
    SELECT 'finance_transaction_proposal', p.id, p.keycloak_subject
      FROM finance_transaction_proposals p
    UNION ALL
    SELECT 'finance_connector', c.id, c.keycloak_subject FROM finance_connectors c
    UNION ALL
    SELECT 'tool_invocation', i.id, i.keycloak_subject FROM tool_invocations i
)
"""


def upgrade() -> None:
    op.add_column("audit_records", sa.Column("keycloak_subject", sa.String(length=255), nullable=True))
    op.add_column("outbox_events", sa.Column("keycloak_subject", sa.String(length=255), nullable=True))

    # Existing user-world outbox rows can be deterministically attributed from the aggregate.
    op.execute(
        _OWNER_CTE
        + r"""
        UPDATE outbox_events AS e
           SET keycloak_subject = owners.keycloak_subject
          FROM owners
         WHERE e.keycloak_subject IS NULL
           AND owners.entity_id = e.aggregate_id
           AND owners.kind = CASE
               WHEN replace(replace(lower(e.aggregate_type), '-', '_'), '.', '_') = 'workflow'
                   THEN 'workflow_execution'
               WHEN replace(replace(lower(e.aggregate_type), '-', '_'), '.', '_') = 'execution'
                   THEN 'workflow_execution'
               WHEN replace(replace(lower(e.aggregate_type), '-', '_'), '.', '_') = 'approval'
                   THEN 'approval_request'
               WHEN replace(replace(lower(e.aggregate_type), '-', '_'), '.', '_') = 'automation_definition'
                   THEN 'automation'
               ELSE replace(replace(lower(e.aggregate_type), '-', '_'), '.', '_')
           END
        """
    )

    # Audit resource_id is textual because some shared/system resources are not UUIDs. Cast only
    # UUID-shaped IDs; shared control-plane rows intentionally stay NULL.
    op.execute(
        _OWNER_CTE
        + r"""
        UPDATE audit_records AS a
           SET keycloak_subject = owners.keycloak_subject
          FROM owners
         WHERE a.keycloak_subject IS NULL
           AND a.resource_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           AND owners.entity_id = a.resource_id::uuid
           AND owners.kind = CASE
               WHEN replace(replace(lower(a.resource_type), '-', '_'), '.', '_') = 'workflow'
                   THEN 'workflow_execution'
               WHEN replace(replace(lower(a.resource_type), '-', '_'), '.', '_') = 'execution'
                   THEN 'workflow_execution'
               WHEN replace(replace(lower(a.resource_type), '-', '_'), '.', '_') = 'approval'
                   THEN 'approval_request'
               WHEN replace(replace(lower(a.resource_type), '-', '_'), '.', '_') = 'automation_definition'
                   THEN 'automation'
               ELSE replace(replace(lower(a.resource_type), '-', '_'), '.', '_')
           END
        """
    )

    op.create_index(
        "ix_audit_subject_created",
        "audit_records",
        ["keycloak_subject", "created_at"],
    )
    op.create_index(
        "ix_audit_user_actor_created",
        "audit_records",
        ["actor_type", "actor_id", "created_at"],
    )
    op.create_index(
        "ix_outbox_subject_created",
        "outbox_events",
        ["keycloak_subject", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_subject_created", table_name="outbox_events")
    op.drop_index("ix_audit_user_actor_created", table_name="audit_records")
    op.drop_index("ix_audit_subject_created", table_name="audit_records")
    op.drop_column("outbox_events", "keycloak_subject")
    op.drop_column("audit_records", "keycloak_subject")
