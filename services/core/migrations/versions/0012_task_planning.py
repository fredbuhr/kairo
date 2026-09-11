"""Add canonical planning metadata to Tasks.

Revision ID: 0012_task_planning
Revises: 0011_tool_invocation_ownership

Today, Calendar and Gantt must share one planning source of truth. Dates and priority therefore live
on canonical Task rows rather than in capability-specific JSON payloads.
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_task_planning"
down_revision = "0011_tool_invocation_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "tasks",
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_tasks_priority_range",
        "tasks",
        "priority >= 0 AND priority <= 4",
    )
    op.create_check_constraint(
        "ck_tasks_planned_window",
        "tasks",
        "planned_end_at IS NULL OR "
        "(planned_start_at IS NOT NULL AND planned_end_at >= planned_start_at)",
    )
    op.create_index("ix_tasks_due_status", "tasks", ["due_at", "status"])
    op.create_index(
        "ix_tasks_planned_window",
        "tasks",
        ["planned_start_at", "planned_end_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_planned_window", table_name="tasks")
    op.drop_index("ix_tasks_due_status", table_name="tasks")
    op.drop_constraint("ck_tasks_planned_window", "tasks", type_="check")
    op.drop_constraint("ck_tasks_priority_range", "tasks", type_="check")
    op.drop_column("tasks", "due_at")
    op.drop_column("tasks", "planned_end_at")
    op.drop_column("tasks", "planned_start_at")
    op.drop_column("tasks", "priority")
