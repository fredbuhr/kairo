"""Add owner-scoped UI workspace layouts.

Revision ID: 0008_workspace_layouts
Revises: 0007_mcp_tool_registry
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_workspace_layouts"
down_revision = "0007_mcp_tool_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_layouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_ref", sa.String(length=320), nullable=False),
        sa.Column("workspace_key", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("layout_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_ref",
            "workspace_key",
            name="uq_workspace_layout_subject_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("workspace_layouts")
