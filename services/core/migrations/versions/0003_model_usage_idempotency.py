"""Add a canonical idempotency key to model usage records.

Revision ID: 0003_model_usage_idempotency
Revises: 0002_autonomy_boundary
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_model_usage_idempotency"
down_revision = "0002_autonomy_boundary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_usage_records",
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
    )
    # PostgreSQL unique indexes allow multiple NULL values, so legacy rows remain valid while every
    # new durable model invocation can claim exactly one canonical ledger entry.
    op.create_index(
        "ux_model_usage_idempotency_key",
        "model_usage_records",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_model_usage_idempotency_key", table_name="model_usage_records")
    op.drop_column("model_usage_records", "idempotency_key")
