"""Add canonical document ingestion and chunk provenance tables.

Revision ID: 0006_document_ingestion
Revises: 0005_memory_projections
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_document_ingestion"
down_revision = "0005_memory_projections"
branch_labels = None
depends_on = None

DOCUMENTS_PROJECT_ID = "a8da482d-fb63-52b5-a687-0f65d64b10ad"


def upgrade() -> None:
    # This is a fixed, migration-owned system UUID. Keep the PostgreSQL type
    # explicit so asyncpg cannot infer the literal as VARCHAR.
    op.execute(
        sa.text(
            f"""
            INSERT INTO projects (id, name, status, summary, parent_id)
            VALUES ('{DOCUMENTS_PROJECT_ID}'::uuid, 'KAIRO Documents', 'active',
                    'System workspace for canonical document ingestion and provenance.', NULL)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text(f"'{DOCUMENTS_PROJECT_ID}'::uuid"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=320), nullable=False),
        sa.Column("media_type", sa.String(length=240), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
    )
    op.create_index("ix_documents_project_status", "documents", ["project_id", "status"])

    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parser", sa.String(length=120), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "generation", name="uq_document_version_generation"),
    )
    op.create_index(
        "ix_document_versions_document_status", "document_versions", ["document_id", "status"]
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_version_id", "ordinal", name="uq_document_chunk_ordinal"),
    )
    op.create_index("ix_document_chunks_version", "document_chunks", ["document_version_id", "ordinal"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_version", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_document_versions_document_status", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_project_status", table_name="documents")
    op.drop_table("documents")
