"""Add authenticated ownership to canonical Projects and explicit Relationships.

Revision ID: 0013_canonical_project_relationship_ownership
Revises: 0012_finance_connectors

Project ownership is the root ownership boundary for Tasks, WorkflowExecutions, Artifacts and most
specialist work. Explicit Relationship rows carry the same owner directly because their endpoints
are polymorphic and cannot safely infer an owner from a single foreign key.

Legacy rows created before authenticated ownership are assigned to the isolated development subject.
Known migration/system workspaces remain system-owned. This keeps old local fixtures visible only in
explicit auth-disabled development stacks; authenticated users create their own system workspaces.
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_canonical_project_relationship_ownership"
down_revision = "0012_finance_connectors"
branch_labels = None
depends_on = None

_DEVELOPMENT_SUBJECT = "development-user"
_SYSTEM_SUBJECT = "__kairo_system__"
_SYSTEM_PROJECT_IDS = (
    "91d3685b-02fb-4fb8-8778-9b9769f3739e",  # legacy Assistant workspace
    "b8d9cccf-257b-4b48-b58e-4fe63a4398b2",  # legacy News workspace
    "a8da482d-fb63-52b5-a687-0f65d64b10ad",  # legacy Documents workspace
)


def upgrade() -> None:
    op.add_column("projects", sa.Column("keycloak_subject", sa.String(length=255), nullable=True))
    op.add_column(
        "relationships", sa.Column("keycloak_subject", sa.String(length=255), nullable=True)
    )

    op.execute(
        sa.text(
            "UPDATE projects SET keycloak_subject = :subject WHERE keycloak_subject IS NULL"
        ).bindparams(subject=_DEVELOPMENT_SUBJECT)
    )
    op.execute(
        sa.text(
            """
            UPDATE projects
               SET keycloak_subject = :system_subject
             WHERE id = ANY(CAST(:system_ids AS uuid[]))
            """
        ).bindparams(system_subject=_SYSTEM_SUBJECT, system_ids=list(_SYSTEM_PROJECT_IDS))
    )
    op.execute(
        sa.text(
            "UPDATE relationships SET keycloak_subject = :subject WHERE keycloak_subject IS NULL"
        ).bindparams(subject=_DEVELOPMENT_SUBJECT)
    )

    op.alter_column("projects", "keycloak_subject", nullable=False)
    op.alter_column("relationships", "keycloak_subject", nullable=False)
    op.create_index(
        "ix_projects_subject_status_updated",
        "projects",
        ["keycloak_subject", "status", "updated_at"],
    )
    op.create_index(
        "ix_relationships_subject_source",
        "relationships",
        ["keycloak_subject", "source_type", "source_id"],
    )
    op.create_index(
        "ix_relationships_subject_target",
        "relationships",
        ["keycloak_subject", "target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_relationships_subject_target", table_name="relationships")
    op.drop_index("ix_relationships_subject_source", table_name="relationships")
    op.drop_index("ix_projects_subject_status_updated", table_name="projects")
    op.drop_column("relationships", "keycloak_subject")
    op.drop_column("projects", "keycloak_subject")
