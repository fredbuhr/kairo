"""Scope ToolInvocation ownership and idempotency to the authenticated subject.

Revision ID: 0011_tool_invocation_ownership
Revises: 0010_relationship_ownership

Tool definitions are deployment-global control-plane records, but invocations are user-world work
bound to a Task and Project. Backfill ownership through Task -> Project, make caller idempotency
subject-local, and enforce the binding at the database boundary.
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_tool_invocation_ownership"
down_revision = "0010_relationship_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tool_invocations",
        sa.Column("owner_subject", sa.String(length=320), nullable=True),
    )
    op.execute(
        """
        UPDATE tool_invocations AS invocation
           SET owner_subject = COALESCE(project.owner_subject, 'development-user')
          FROM tasks AS task
          JOIN projects AS project ON project.id = task.project_id
         WHERE invocation.task_id = task.id
           AND invocation.owner_subject IS NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM tool_invocations WHERE owner_subject IS NULL) THEN
                RAISE EXCEPTION 'ToolInvocation ownership could not be derived from Task -> Project'
                    USING ERRCODE = '23514';
            END IF;
        END;
        $$;
        """
    )
    op.alter_column("tool_invocations", "owner_subject", nullable=False)

    op.execute(
        "ALTER TABLE tool_invocations "
        "DROP CONSTRAINT IF EXISTS tool_invocations_idempotency_key_key"
    )
    op.create_unique_constraint(
        "uq_tool_invocation_owner_idempotency",
        "tool_invocations",
        ["owner_subject", "idempotency_key"],
    )
    op.create_index(
        "ix_tool_invocations_owner_status",
        "tool_invocations",
        ["owner_subject", "status", "created_at"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION kairo_enforce_tool_invocation_task_owner()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM tasks AS task
                JOIN projects AS project ON project.id = task.project_id
                WHERE task.id = NEW.task_id
                  AND COALESCE(project.owner_subject, 'development-user') = NEW.owner_subject
            ) THEN
                RAISE EXCEPTION 'tool invocation Task is outside the authenticated owner scope'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tool_invocation_task_owner
        BEFORE INSERT OR UPDATE OF task_id, owner_subject
        ON tool_invocations
        FOR EACH ROW
        EXECUTE FUNCTION kairo_enforce_tool_invocation_task_owner();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_tool_invocation_task_owner ON tool_invocations"
    )
    op.execute("DROP FUNCTION IF EXISTS kairo_enforce_tool_invocation_task_owner()")
    op.drop_index("ix_tool_invocations_owner_status", table_name="tool_invocations")
    op.drop_constraint(
        "uq_tool_invocation_owner_idempotency",
        "tool_invocations",
        type_="unique",
    )
    op.create_unique_constraint(
        "tool_invocations_idempotency_key_key",
        "tool_invocations",
        ["idempotency_key"],
    )
    op.drop_column("tool_invocations", "owner_subject")
