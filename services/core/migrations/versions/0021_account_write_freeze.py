"""Add a durable local write freeze for account-erasure preparation.

Revision ID: 0021_account_write_freeze
Revises: 0020_outbox_jetstream_receipts
Create Date: 2026-09-10

Keycloak disable cannot by itself reject already-issued access tokens. KAIRO therefore needs a local
canonical barrier which is checked before public user-originated mutations. Row existence means the
subject is frozen. Internal service routes remain outside this table's public-write perimeter so
already-started durable work can still reconcile to a terminal state.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_account_write_freeze"
down_revision = "0020_outbox_jetstream_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_write_freezes",
        sa.Column("keycloak_subject", sa.String(length=255), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "reason",
            sa.String(length=320),
            nullable=False,
            server_default="account_erasure_preparation",
        ),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("keycloak_subject", name="pk_account_write_freezes"),
        sa.UniqueConstraint("operation_id", name="uq_account_write_freezes_operation_id"),
    )
    op.create_index(
        "ix_account_write_freezes_frozen_at",
        "account_write_freezes",
        ["frozen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_write_freezes_frozen_at", table_name="account_write_freezes")
    op.drop_table("account_write_freezes")
