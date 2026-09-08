"""Add rebuildable memory projection tracking.

Revision ID: 0005_memory_projections
Revises: 0004_command_kernel
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_memory_projections"
down_revision = "0004_command_kernel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("projector", sa.String(length=64), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("projection_key", sa.String(length=320), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "source_type",
            "source_id",
            "source_version",
            "projector",
            name="uq_memory_projection_source_projector",
        ),
    )
    op.create_index("ix_memory_projections_status", "memory_projections", ["status"])
    op.create_index(
        "ix_memory_projections_source",
        "memory_projections",
        ["source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_projections_source", table_name="memory_projections")
    op.drop_index("ix_memory_projections_status", table_name="memory_projections")
    op.drop_table("memory_projections")
