"""Add a durable account-erasure preparation operation ledger.

Revision ID: 0022_account_erasure_operation
Revises: 0021_account_write_freeze
Create Date: 2026-09-10

This migration does not add destructive account deletion. It creates the canonical operation identity
which will own future replay-safe erasure phases. At most one preparing/ready operation may exist per
subject while cancelled history remains available for audit/reconciliation.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022_account_erasure_operation"
down_revision = "0021_account_write_freeze"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_erasure_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keycloak_subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="preparing"),
        sa.Column("phase", sa.String(length=64), nullable=False, server_default="write_freeze"),
        sa.Column("freeze_operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owns_write_freeze", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "blocker_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("irreversible_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_account_erasure_operations"),
    )
    op.create_index(
        "ix_account_erasure_subject_created",
        "account_erasure_operations",
        ["keycloak_subject", "created_at"],
    )
    op.create_index(
        "uq_account_erasure_active_subject",
        "account_erasure_operations",
        ["keycloak_subject"],
        unique=True,
        postgresql_where=sa.text("status IN ('preparing', 'ready')"),
    )


def downgrade() -> None:
    op.drop_index("uq_account_erasure_active_subject", table_name="account_erasure_operations")
    op.drop_index("ix_account_erasure_subject_created", table_name="account_erasure_operations")
    op.drop_table("account_erasure_operations")
