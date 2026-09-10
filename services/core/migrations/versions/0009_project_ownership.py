"""Add canonical Project ownership.

Revision ID: 0009_project_ownership
Revises: 0008_workspace_layouts
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_project_ownership"
down_revision = "0008_workspace_layouts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("owner_subject", sa.String(length=320), nullable=True))
    op.create_index("ix_projects_owner_status", "projects", ["owner_subject", "status"])


def downgrade() -> None:
    op.drop_index("ix_projects_owner_status", table_name="projects")
    op.drop_column("projects", "owner_subject")
