"""Persist JetStream publication receipts for Outbox retention reconciliation.

Revision ID: 0020_outbox_jetstream_receipts
Revises: 0019_audit_outbox_data_subject
Create Date: 2026-09-09

Newly published Outbox rows record the JetStream stream + sequence returned by the server. Historical
published rows intentionally remain unmapped because their exact sequence cannot be reconstructed
safely after the fact. Account-erasure preflight exposes those rows as a migration/retention blocker
rather than pretending they can be surgically deleted from JetStream.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0020_outbox_jetstream_receipts"
down_revision = "0019_audit_outbox_data_subject"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("jetstream_stream", sa.String(length=120), nullable=True))
    op.add_column("outbox_events", sa.Column("jetstream_sequence", sa.BigInteger(), nullable=True))
    op.create_unique_constraint(
        "uq_outbox_jetstream_receipt",
        "outbox_events",
        ["jetstream_stream", "jetstream_sequence"],
    )
    op.create_index(
        "ix_outbox_subject_receipt",
        "outbox_events",
        ["keycloak_subject", "jetstream_stream", "jetstream_sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_subject_receipt", table_name="outbox_events")
    op.drop_constraint("uq_outbox_jetstream_receipt", "outbox_events", type_="unique")
    op.drop_column("outbox_events", "jetstream_sequence")
    op.drop_column("outbox_events", "jetstream_stream")
