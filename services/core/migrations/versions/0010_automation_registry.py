"""Add canonical automation definitions and invocation ledger.

Revision ID: 0010_automation_registry
Revises: 0009_external_calendar_snapshots
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_automation_registry"
down_revision = "0009_external_calendar_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keycloak_subject", sa.String(length=240), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("engine", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("authority_level", sa.Integer(), nullable=False),
        sa.Column("webhook_secret_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("webhook_secret_key", sa.String(length=120), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["webhook_secret_reference_id"],
            ["secret_references.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keycloak_subject", "key", name="uq_automation_definition_subject_key"),
    )
    op.create_index(
        "ix_automation_definitions_subject_enabled",
        "automation_definitions",
        ["keycloak_subject", "enabled"],
        unique=False,
    )
    op.create_index(
        "ix_automation_definitions_project",
        "automation_definitions",
        ["project_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "automation_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("automation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("outcome_ambiguous", sa.Boolean(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["automation_id"], ["automation_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workflow_execution_id"],
            ["workflow_executions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_automation_invocations_automation_created",
        "automation_invocations",
        ["automation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_automation_invocations_status_created",
        "automation_invocations",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_automation_invocations_correlation",
        "automation_invocations",
        ["correlation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_automation_invocations_correlation", table_name="automation_invocations")
    op.drop_index("ix_automation_invocations_status_created", table_name="automation_invocations")
    op.drop_index("ix_automation_invocations_automation_created", table_name="automation_invocations")
    op.drop_table("automation_invocations")
    op.drop_index("ix_automation_definitions_project", table_name="automation_definitions")
    op.drop_index("ix_automation_definitions_subject_enabled", table_name="automation_definitions")
    op.drop_table("automation_definitions")
