"""Add canonical MCP tool registry and invocation ledger.

Revision ID: 0007_mcp_tool_registry
Revises: 0006_document_ingestion
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_mcp_tool_registry"
down_revision = "0006_document_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("namespace", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("transport", sa.String(length=64), nullable=False),
        sa.Column("endpoint_url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("catalog_generation", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
        sa.UniqueConstraint("namespace"),
    )

    op.create_table(
        "tool_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("remote_name", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("remote_annotations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("schema_hash", sa.String(length=64), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("authority_level", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 4), nullable=False),
        sa.Column("risk_class", sa.String(length=32), nullable=False),
        sa.Column("retry_policy", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["tool_servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
        sa.UniqueConstraint("server_id", "remote_name", name="uq_tool_definition_server_remote"),
    )
    op.create_index("ix_tool_definitions_server_available", "tool_definitions", ["server_id", "available"])
    op.create_index("ix_tool_definitions_enabled_available", "tool_definitions", ["enabled", "available"])

    op.create_table(
        "tool_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authority_level", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 4), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tool_definition_id"], ["tool_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_execution_id"], ["workflow_executions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_tool_invocations_task_status", "tool_invocations", ["task_id", "status"])
    op.create_index("ix_tool_invocations_correlation", "tool_invocations", ["correlation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_invocations_correlation", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_task_status", table_name="tool_invocations")
    op.drop_table("tool_invocations")
    op.drop_index("ix_tool_definitions_enabled_available", table_name="tool_definitions")
    op.drop_index("ix_tool_definitions_server_available", table_name="tool_definitions")
    op.drop_table("tool_definitions")
    op.drop_table("tool_servers")
