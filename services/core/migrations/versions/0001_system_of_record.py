"""Create the Nevolium canonical system-of-record tables.

Revision ID: 0001_system_of_record
Revises:
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_system_of_record"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def _uuid() -> sa.TextClause:
    return sa.text("gen_random_uuid()")


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "projects",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("summary", sa.Text()),
        sa.Column("parent_id", UUID, sa.ForeignKey("projects.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
    )

    op.create_table(
        "tasks",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="todo"),
        sa.Column("owner_type", sa.String(32), nullable=False, server_default="user"),
        sa.Column("owner_ref", sa.String(240)),
        sa.Column("authority_ceiling", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("budget_usd", sa.Numeric(12, 4)),
        sa.Column("input", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
    )
    op.create_index("ix_tasks_project_status", "tasks", ["project_id", "status"])

    op.create_table(
        "relationships",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("relation_type", sa.String(96), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", UUID, nullable=False),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
    )
    op.create_index("ix_relationships_source", "relationships", ["source_type", "source_id"])
    op.create_index("ix_relationships_target", "relationships", ["target_type", "target_id"])

    op.create_table(
        "workflow_executions",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("task_id", UUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.String(320), nullable=False, unique=True),
        sa.Column("run_id", sa.String(160)),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_start"),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
    )
    op.create_index(
        "ix_workflow_executions_task_status", "workflow_executions", ["task_id", "status"]
    )

    op.create_table(
        "artifacts",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", UUID, sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column(
            "workflow_execution_id",
            UUID,
            sa.ForeignKey("workflow_executions.id", ondelete="SET NULL"),
            unique=True,
        ),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("content", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
    )

    op.create_table(
        "assets",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="SET NULL")),
        sa.Column("bucket", sa.String(120), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(240)),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("sha256", sa.String(64)),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.UniqueConstraint("bucket", "object_key", name="uq_assets_object"),
    )

    op.create_table(
        "device_registrations",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("keycloak_subject", sa.String(240), nullable=False),
        sa.Column("device_key", sa.String(240), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("capabilities", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("public_key", sa.Text()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.UniqueConstraint("keycloak_subject", "device_key", name="uq_device_subject_key"),
    )

    op.create_table(
        "secret_references",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("provider_path", sa.String(1024), nullable=False, unique=True),
        sa.Column("purpose", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
    )

    op.create_table(
        "audit_records",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("actor_type", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(240)),
        sa.Column("action", sa.String(160), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(240), nullable=False),
        sa.Column("authority_level", sa.Integer(), nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("idempotency_key", sa.String(320)),
        sa.Column("request_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
    )
    op.create_index("ix_audit_correlation", "audit_records", ["correlation_id", "created_at"])

    op.create_table(
        "outbox_events",
        sa.Column("id", UUID, primary_key=True, server_default=_uuid()),
        sa.Column("subject", sa.String(240), nullable=False),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events", ["published_at", "created_at"])
    op.create_index("ix_outbox_correlation", "outbox_events", ["correlation_id"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("audit_records")
    op.drop_table("secret_references")
    op.drop_table("device_registrations")
    op.drop_table("assets")
    op.drop_table("artifacts")
    op.drop_table("workflow_executions")
    op.drop_table("relationships")
    op.drop_table("tasks")
    op.drop_table("projects")
