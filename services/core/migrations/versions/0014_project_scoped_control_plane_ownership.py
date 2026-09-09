"""enforce project-subject ownership for project-scoped control-plane records

Revision ID: 0014_project_scoped_control_plane_ownership
Revises: 0013_canonical_project_relationship_ownership
Create Date: 2026-09-09
"""

from __future__ import annotations

from alembic import op

revision = "0014_project_scoped_control_plane_ownership"
down_revision = "0013_canonical_project_relationship_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires a unique target for a composite FK even though Project.id is already the
    # primary key. The pair makes the ownership invariant explicit at the database boundary.
    op.create_unique_constraint(
        "uq_projects_id_keycloak_subject",
        "projects",
        ["id", "keycloak_subject"],
    )

    op.create_foreign_key(
        "fk_automation_definitions_project_subject",
        "automation_definitions",
        "projects",
        ["project_id", "keycloak_subject"],
        ["id", "keycloak_subject"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_finance_connectors_project_subject",
        "finance_connectors",
        "projects",
        ["project_id", "keycloak_subject"],
        ["id", "keycloak_subject"],
        ondelete="CASCADE",
    )

    # Finance proposals have a nullable project_id with an existing ON DELETE SET NULL FK. A
    # composite SET NULL FK would also attempt to null the non-null subject, so use a narrow trigger
    # to enforce the same owner only while a Project is attached.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION kairo_enforce_finance_proposal_project_owner()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.project_id IS NOT NULL AND NOT EXISTS (
                SELECT 1
                FROM projects p
                WHERE p.id = NEW.project_id
                  AND p.keycloak_subject = NEW.keycloak_subject
            ) THEN
                RAISE EXCEPTION 'finance proposal project is outside the authenticated owner scope'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_finance_proposal_project_owner
        BEFORE INSERT OR UPDATE OF project_id, keycloak_subject
        ON finance_transaction_proposals
        FOR EACH ROW
        EXECUTE FUNCTION kairo_enforce_finance_proposal_project_owner();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_finance_proposal_project_owner ON finance_transaction_proposals"
    )
    op.execute("DROP FUNCTION IF EXISTS kairo_enforce_finance_proposal_project_owner()")
    op.drop_constraint(
        "fk_finance_connectors_project_subject",
        "finance_connectors",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_automation_definitions_project_subject",
        "automation_definitions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_projects_id_keycloak_subject",
        "projects",
        type_="unique",
    )
