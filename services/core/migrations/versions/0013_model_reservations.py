"""Durable model admission and estimated budget reservations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_model_reservations"
down_revision = "0012_task_planning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_reservations",
        sa.Column("idempotency_key", sa.String(160), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_executions.id", ondelete="SET NULL")),
        sa.Column("owner_subject", sa.String(320), nullable=False),
        sa.Column("model_alias", sa.String(120), nullable=False),
        sa.Column("amount_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_usd >= 0", name="ck_model_reservation_amount"),
        sa.CheckConstraint("status IN ('reserved', 'started', 'settled', 'uncertain', 'expired')", name="ck_model_reservation_status"),
    )
    op.create_index("ix_model_reservation_task", "model_reservations", ["task_id", "status"])
    op.create_index("ix_model_reservation_owner", "model_reservations", ["owner_subject", "status"])
    op.create_index("ix_model_reservation_expiry", "model_reservations", ["status", "expires_at"])
    op.create_index("ix_model_usage_created", "model_usage_records", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_model_usage_created", table_name="model_usage_records")
    op.drop_table("model_reservations")
