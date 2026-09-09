"""Promote Asset/Document owner metadata into explicit canonical ownership columns.

Revision ID: 0018_asset_document_ownership
Revises: 0017_tool_invocation_ownership
Create Date: 2026-09-09

Assets and Documents historically carried owner_subject inside JSON metadata. That was enough for the
single-user prototype but makes tenant scoping easier to omit, harder to index and harder to enforce
at the database boundary. This migration promotes ownership into first-class columns while preserving
legacy rows. Future Project/Asset bindings are checked by triggers; historical system-workspace rows
may remain mismatched until their existing compatibility rehome path touches them.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0018_asset_document_ownership"
down_revision = "0017_tool_invocation_ownership"
branch_labels = None
depends_on = None

_DEVELOPMENT_SUBJECT = "development-user"


def upgrade() -> None:
    op.add_column("assets", sa.Column("keycloak_subject", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("keycloak_subject", sa.String(length=255), nullable=True))

    # Prefer the explicit historical owner tag when present. Fall back to the Project root for rows
    # that predate owner metadata, then finally to the isolated development subject.
    op.execute(
        """
        UPDATE assets
           SET keycloak_subject = NULLIF(metadata_json->>'owner_subject', '')
         WHERE keycloak_subject IS NULL
        """
    )
    op.execute(
        """
        UPDATE assets AS a
           SET keycloak_subject = p.keycloak_subject
          FROM projects AS p
         WHERE a.keycloak_subject IS NULL
           AND a.project_id = p.id
        """
    )
    op.execute(
        sa.text(
            "UPDATE assets SET keycloak_subject = :subject WHERE keycloak_subject IS NULL"
        ).bindparams(subject=_DEVELOPMENT_SUBJECT)
    )

    op.execute(
        """
        UPDATE documents
           SET keycloak_subject = NULLIF(metadata_json->>'owner_subject', '')
         WHERE keycloak_subject IS NULL
        """
    )
    op.execute(
        """
        UPDATE documents AS d
           SET keycloak_subject = p.keycloak_subject
          FROM projects AS p
         WHERE d.keycloak_subject IS NULL
           AND d.project_id = p.id
        """
    )
    op.execute(
        sa.text(
            "UPDATE documents SET keycloak_subject = :subject WHERE keycloak_subject IS NULL"
        ).bindparams(subject=_DEVELOPMENT_SUBJECT)
    )

    op.alter_column("assets", "keycloak_subject", nullable=False)
    op.alter_column("documents", "keycloak_subject", nullable=False)

    op.create_index(
        "ix_assets_subject_created",
        "assets",
        ["keycloak_subject", "created_at"],
    )
    op.create_index(
        "ix_documents_subject_status_updated",
        "documents",
        ["keycloak_subject", "status", "updated_at"],
    )

    # Assets may be unscoped. When a Project is attached, future inserts/rebindings must agree with
    # the Project owner. ON DELETE SET NULL remains valid because NULL project_id bypasses the check.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION kairo_enforce_asset_project_owner()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.project_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM projects p
                 WHERE p.id = NEW.project_id
                   AND p.keycloak_subject = NEW.keycloak_subject
            ) THEN
                RAISE EXCEPTION 'asset project is outside the authenticated owner scope'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_asset_project_owner
        BEFORE INSERT OR UPDATE OF project_id, keycloak_subject
        ON assets
        FOR EACH ROW
        EXECUTE FUNCTION kairo_enforce_asset_project_owner();
        """
    )

    # Documents always bind both a Project and a source Asset. New/rebound rows must keep all three
    # ownership identities aligned. Historical rows are not rewritten merely to satisfy the trigger;
    # the existing reingest compatibility path rehomes known legacy Documents when touched.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION kairo_enforce_document_owner_bindings()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM projects p
                 WHERE p.id = NEW.project_id
                   AND p.keycloak_subject = NEW.keycloak_subject
            ) THEN
                RAISE EXCEPTION 'document project is outside the authenticated owner scope'
                    USING ERRCODE = '23503';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM assets a
                 WHERE a.id = NEW.asset_id
                   AND a.keycloak_subject = NEW.keycloak_subject
            ) THEN
                RAISE EXCEPTION 'document asset is outside the authenticated owner scope'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_document_owner_bindings
        BEFORE INSERT OR UPDATE OF project_id, asset_id, keycloak_subject
        ON documents
        FOR EACH ROW
        EXECUTE FUNCTION kairo_enforce_document_owner_bindings();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_document_owner_bindings ON documents")
    op.execute("DROP FUNCTION IF EXISTS kairo_enforce_document_owner_bindings()")
    op.execute("DROP TRIGGER IF EXISTS trg_asset_project_owner ON assets")
    op.execute("DROP FUNCTION IF EXISTS kairo_enforce_asset_project_owner()")
    op.drop_index("ix_documents_subject_status_updated", table_name="documents")
    op.drop_index("ix_assets_subject_created", table_name="assets")
    op.drop_column("documents", "keycloak_subject")
    op.drop_column("assets", "keycloak_subject")
