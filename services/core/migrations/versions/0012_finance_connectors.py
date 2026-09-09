"""Add KAIRO-owned finance connector configuration.

Revision ID: 0012_finance_connectors
Revises: 0011_finance_portfolio_snapshots
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012_finance_connectors"
down_revision = "0011_finance_portfolio_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_connectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keycloak_subject", sa.String(length=240), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("secret_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username_secret_key", sa.String(length=120), nullable=False),
        sa.Column("password_secret_key", sa.String(length=120), nullable=False),
        sa.Column("source_key", sa.String(length=160), nullable=False),
        sa.Column("refresh_remote", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["secret_reference_id"], ["secret_references.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keycloak_subject", "key", name="uq_finance_connector_subject_key"),
        sa.UniqueConstraint(
            "keycloak_subject",
            "source_key",
            name="uq_finance_connector_subject_source_key",
        ),
    )
    op.create_index(
        "ix_finance_connectors_subject_enabled",
        "finance_connectors",
        ["keycloak_subject", "enabled"],
        unique=False,
    )
    op.create_index(
        "ix_finance_connectors_project",
        "finance_connectors",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_finance_connectors_project", table_name="finance_connectors")
    op.drop_index("ix_finance_connectors_subject_enabled", table_name="finance_connectors")
    op.drop_table("finance_connectors")
