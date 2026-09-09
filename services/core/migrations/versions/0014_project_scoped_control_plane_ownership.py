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


def downgrade() -> None:
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
