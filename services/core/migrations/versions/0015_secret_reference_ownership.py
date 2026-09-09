"""Scope SecretReferences by authenticated subject and bind connector references to the same owner.

Revision ID: 0015_secret_reference_ownership
Revises: 0014_project_scoped_control_plane_ownership
Create Date: 2026-09-09

SecretReference rows point at OpenBao locations that can unlock external integrations. They are user
world metadata, not a deployment-global registry. Existing references are assigned to the unique
owner already using them when one exists; unbound legacy rows stay with the isolated development
subject. A reference already shared across different subjects is treated as a migration-time safety
violation instead of being silently reassigned.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_secret_reference_ownership"
down_revision = "0014_project_scoped_control_plane_ownership"
branch_labels = None
depends_on = None

_DEVELOPMENT_SUBJECT = "development-user"


def upgrade() -> None:
    op.add_column(
        "secret_references",
        sa.Column("keycloak_subject", sa.String(length=255), nullable=True),
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                WITH refs AS (
                    SELECT webhook_secret_reference_id AS reference_id, keycloak_subject
                    FROM automation_definitions
                    UNION ALL
                    SELECT secret_reference_id AS reference_id, keycloak_subject
                    FROM finance_connectors
                )
                SELECT 1
                FROM refs
                GROUP BY reference_id
                HAVING count(DISTINCT keycloak_subject) > 1
            ) THEN
                RAISE EXCEPTION 'a SecretReference is already shared by multiple authenticated subjects'
                    USING ERRCODE = '23514';
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        sa.text(
            """
            WITH refs AS (
                SELECT webhook_secret_reference_id AS reference_id, keycloak_subject
                FROM automation_definitions
                UNION ALL
                SELECT secret_reference_id AS reference_id, keycloak_subject
                FROM finance_connectors
            ), unique_owner AS (
                SELECT reference_id, min(keycloak_subject) AS keycloak_subject
                FROM refs
                GROUP BY reference_id
            )
            UPDATE secret_references AS secret
               SET keycloak_subject = COALESCE(owner.keycloak_subject, :development_subject)
              FROM (SELECT 1) AS anchor
              LEFT JOIN unique_owner AS owner ON owner.reference_id = secret.id
             WHERE secret.keycloak_subject IS NULL
            """
        ).bindparams(development_subject=_DEVELOPMENT_SUBJECT)
    )

    op.alter_column("secret_references", "keycloak_subject", nullable=False)
    op.create_index(
        "ix_secret_references_subject_created",
        "secret_references",
        ["keycloak_subject", "created_at"],
    )
    op.create_unique_constraint(
        "uq_secret_references_id_keycloak_subject",
        "secret_references",
        ["id", "keycloak_subject"],
    )

    op.create_foreign_key(
        "fk_automation_definitions_secret_subject",
        "automation_definitions",
        "secret_references",
        ["webhook_secret_reference_id", "keycloak_subject"],
        ["id", "keycloak_subject"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_finance_connectors_secret_subject",
        "finance_connectors",
        "secret_references",
        ["secret_reference_id", "keycloak_subject"],
        ["id", "keycloak_subject"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_finance_connectors_secret_subject",
        "finance_connectors",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_automation_definitions_secret_subject",
        "automation_definitions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_secret_references_id_keycloak_subject",
        "secret_references",
        type_="unique",
    )
    op.drop_index("ix_secret_references_subject_created", table_name="secret_references")
    op.drop_column("secret_references", "keycloak_subject")
