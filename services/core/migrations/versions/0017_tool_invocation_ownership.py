"""Scope ToolInvocation idempotency to the authenticated subject.

Revision ID: 0017_tool_invocation_ownership
Revises: 0016_automation_idempotency_scope
Create Date: 2026-09-09

Tool definitions are deployment-global control-plane records, but invocations are user-world work tied
to a Task/Project. A caller-selected idempotency key must therefore not remain a deployment-global
namespace. Backfill ownership through Task -> Project, then make the uniqueness boundary subject-local.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0017_tool_invocation_ownership"
down_revision = "0016_automation_idempotency_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tool_invocations",
        sa.Column("keycloak_subject", sa.String(length=240), nullable=True),
    )
    op.execute(
        """
        UPDATE tool_invocations AS invocation
           SET keycloak_subject = project.keycloak_subject
          FROM tasks AS task
          JOIN projects AS project ON project.id = task.project_id
         WHERE invocation.task_id = task.id
           AND invocation.keycloak_subject IS NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM tool_invocations WHERE keycloak_subject IS NULL) THEN
                RAISE EXCEPTION 'ToolInvocation ownership could not be derived from Task -> Project'
                    USING ERRCODE = '23514';
            END IF;
        END;
        $$;
        """
    )
    op.alter_column("tool_invocations", "keycloak_subject", nullable=False)

    op.execute(
        "ALTER TABLE tool_invocations "
        "DROP CONSTRAINT IF EXISTS tool_invocations_idempotency_key_key"
    )
    op.create_unique_constraint(
        "uq_tool_invocation_subject_idempotency",
        "tool_invocations",
        ["keycloak_subject", "idempotency_key"],
    )
    op.create_index(
        "ix_tool_invocations_subject_status",
        "tool_invocations",
        ["keycloak_subject", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tool_invocations_subject_status", table_name="tool_invocations")
    op.drop_constraint(
        "uq_tool_invocation_subject_idempotency",
        "tool_invocations",
        type_="unique",
    )
    # This may intentionally fail if different subjects have reused the same idempotency key after
    # the upgrade. Such data cannot be losslessly collapsed back into the old global namespace.
    op.create_unique_constraint(
        "tool_invocations_idempotency_key_key",
        "tool_invocations",
        ["idempotency_key"],
    )
    op.drop_column("tool_invocations", "keycloak_subject")
