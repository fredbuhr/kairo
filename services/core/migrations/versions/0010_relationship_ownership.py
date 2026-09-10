"""Add canonical subject ownership to polymorphic Relationships.

Revision ID: 0010_relationship_ownership
Revises: 0009_project_ownership

Relationships cannot safely infer ownership from one foreign key because both endpoints are
polymorphic. New rows therefore carry the authenticated subject directly. Historical rows are
assigned to the isolated development subject rather than exposed to arbitrary authenticated users.
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_relationship_ownership"
down_revision = "0009_project_ownership"
branch_labels = None
depends_on = None

_DEVELOPMENT_SUBJECT = "development-user"


def upgrade() -> None:
    op.add_column(
        "relationships",
        sa.Column("owner_subject", sa.String(length=320), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE relationships SET owner_subject = :subject WHERE owner_subject IS NULL"
        ).bindparams(subject=_DEVELOPMENT_SUBJECT)
    )
    op.alter_column("relationships", "owner_subject", nullable=False)
    op.create_index(
        "ix_relationships_owner_source",
        "relationships",
        ["owner_subject", "source_type", "source_id"],
    )
    op.create_index(
        "ix_relationships_owner_target",
        "relationships",
        ["owner_subject", "target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_relationships_owner_target", table_name="relationships")
    op.drop_index("ix_relationships_owner_source", table_name="relationships")
    op.drop_column("relationships", "owner_subject")
