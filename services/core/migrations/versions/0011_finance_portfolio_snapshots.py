"""Add sourced finance portfolio observations and unsigned transaction proposals.

Revision ID: 0011_finance_portfolio_snapshots
Revises: 0010_automation_registry
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0011_finance_portfolio_snapshots"
down_revision = "0010_automation_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keycloak_subject", sa.String(length=240), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("external_account_ref", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keycloak_subject", "key", name="uq_finance_source_subject_key"),
        sa.UniqueConstraint(
            "keycloak_subject",
            "provider",
            "external_account_ref",
            name="uq_finance_source_subject_account",
        ),
    )
    op.create_index(
        "ix_finance_sources_subject_status",
        "finance_sources",
        ["keycloak_subject", "status"],
        unique=False,
    )

    op.create_table(
        "finance_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=False),
        sa.Column("label", sa.String(length=240), nullable=False),
        sa.Column("account_type", sa.String(length=64), nullable=False),
        sa.Column("network", sa.String(length=120), nullable=True),
        sa.Column("public_address", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["finance_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_finance_account_source_external"),
    )
    op.create_index(
        "ix_finance_accounts_source_type",
        "finance_accounts",
        ["source_id", "account_type"],
        unique=False,
    )

    op.create_table(
        "finance_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_key", sa.String(length=240), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=True),
        sa.Column("asset_type", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=40, scale=18), nullable=False),
        sa.Column("unit_price_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("value_usd", sa.Numeric(precision=30, scale=10), nullable=False),
        sa.Column("cost_basis_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("unrealized_pnl_usd", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["finance_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "asset_key", name="uq_finance_position_account_asset"),
    )
    op.create_index(
        "ix_finance_positions_account_value",
        "finance_positions",
        ["account_id", "value_usd"],
        unique=False,
    )
    op.create_index(
        "ix_finance_positions_asset",
        "finance_positions",
        ["asset_key"],
        unique=False,
    )

    op.create_table(
        "finance_transaction_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keycloak_subject", sa.String(length=240), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("network", sa.String(length=120), nullable=False),
        sa.Column("asset_key", sa.String(length=240), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=40, scale=18), nullable=False),
        sa.Column("destination", sa.String(length=512), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("estimated_fee_asset", sa.String(length=240), nullable=True),
        sa.Column("estimated_fee_amount", sa.Numeric(precision=40, scale=18), nullable=True),
        sa.Column("simulation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["from_account_id"], ["finance_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_finance_proposals_subject_status",
        "finance_transaction_proposals",
        ["keycloak_subject", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_finance_proposals_account",
        "finance_transaction_proposals",
        ["from_account_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_finance_proposals_account", table_name="finance_transaction_proposals")
    op.drop_index("ix_finance_proposals_subject_status", table_name="finance_transaction_proposals")
    op.drop_table("finance_transaction_proposals")
    op.drop_index("ix_finance_positions_asset", table_name="finance_positions")
    op.drop_index("ix_finance_positions_account_value", table_name="finance_positions")
    op.drop_table("finance_positions")
    op.drop_index("ix_finance_accounts_source_type", table_name="finance_accounts")
    op.drop_table("finance_accounts")
    op.drop_index("ix_finance_sources_subject_status", table_name="finance_sources")
    op.drop_table("finance_sources")
