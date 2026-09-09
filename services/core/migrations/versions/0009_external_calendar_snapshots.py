"""Add provenance-preserving external calendar source snapshots.

Revision ID: 0009_external_calendar_snapshots
Revises: 0008_task_planning_fields
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_external_calendar_snapshots"
down_revision = "0008_task_planning_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keycloak_subject", sa.String(length=240), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_account_ref", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keycloak_subject", "key", name="uq_calendar_source_subject_key"),
        sa.UniqueConstraint(
            "keycloak_subject",
            "provider",
            "external_account_ref",
            name="uq_calendar_source_subject_account",
        ),
    )
    op.create_index(
        "ix_calendar_sources_subject_status",
        "calendar_sources",
        ["keycloak_subject", "status"],
        unique=False,
    )

    op.create_table(
        "external_calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["calendar_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_external_calendar_event_source_external"),
    )
    op.create_index(
        "ix_external_calendar_events_source_start",
        "external_calendar_events",
        ["source_id", "start_at"],
        unique=False,
    )
    op.create_index(
        "ix_external_calendar_events_interval",
        "external_calendar_events",
        ["start_at", "end_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_external_calendar_events_interval", table_name="external_calendar_events")
    op.drop_index("ix_external_calendar_events_source_start", table_name="external_calendar_events")
    op.drop_table("external_calendar_events")
    op.drop_index("ix_calendar_sources_subject_status", table_name="calendar_sources")
    op.drop_table("calendar_sources")
